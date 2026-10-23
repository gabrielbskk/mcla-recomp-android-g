package org.mcla.recomp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.provider.DocumentsContract;

import org.apache.commons.compress.archivers.zip.ZipArchiveEntry;
import org.apache.commons.compress.archivers.zip.ZipArchiveInputStream;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** SAF-backed, foreground import into filesDir/game.part followed by an atomic directory swap. */
public final class DataImportService extends Service {
    static final String ACTION_IMPORT_ZIP = "org.mcla.recomp.IMPORT_ZIP";
    static final String ACTION_IMPORT_FOLDER = "org.mcla.recomp.IMPORT_FOLDER";
    static final String ACTION_PROGRESS = "org.mcla.recomp.IMPORT_PROGRESS";
    static final String EXTRA_INCLUDE_BIK = "include_bik";
    static final String EXTRA_COPIED = "copied";
    static final String EXTRA_TOTAL = "total";
    static final String EXTRA_MESSAGE = "message";
    static final String EXTRA_FINISHED = "finished";
    static final String EXTRA_SUCCESS = "success";

    private static final String CHANNEL_ID = "mcla_import";
    private static final int NOTIFICATION_ID = 4305;
    private static final long MAX_GAME_BYTES = 20L * 1024 * 1024 * 1024;
    private static final long MIN_FREE_RESERVE = 256L * 1024 * 1024;
    private static final int BUFFER_SIZE = 256 * 1024;
    private static final int MAX_TREE_NODES = 100_000;
    private static final int MAX_TREE_DEPTH = 32;
    private static final String[] REQUIRED = {
            "default.xex", "xarchive_cache.rpf", "xarchive_audio.rpf",
            "xarchive_audlo.rpf", "xarchive_music.rpf"
    };
    private static final Set<String> REQUIRED_SET = new HashSet<>(Arrays.asList(REQUIRED));
    private static final String READY_MARKER = ".mcla_ready";

    private volatile boolean cancelled;
    private volatile boolean timedOut;
    private PowerManager.WakeLock wakeLock;
    private long copiedBytes;
    private long totalBytes;
    private String progressMessage = "Importing game data";

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || intent.getData() == null) {
            stopSelf(startId);
            return START_NOT_STICKY;
        }
        createNotificationChannel();
        Notification notification = buildNotification("Preparing import", 0, 0);
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
        acquireWakeLock();
        Uri uri = intent.getData();
        boolean folder = ACTION_IMPORT_FOLDER.equals(intent.getAction());
        boolean includeBik = intent.getBooleanExtra(EXTRA_INCLUDE_BIK, false);
        new Thread(() -> runImport(uri, folder, includeBik, startId), "mcla-private-import").start();
        return START_NOT_STICKY;
    }

    @Override public void onDestroy() {
        cancelled = true;
        releaseWakeLock();
        super.onDestroy();
    }

    /** Android 15 calls this when a dataSync foreground service exceeds its time budget. */
    @Override public void onTimeout(int startId, int foregroundServiceType) {
        timedOut = true;
        cancelled = true;
        sendProgress("Android stopped the import after its time limit. Start the import again to continue.",
                true, false);
        releaseWakeLock();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf(startId);
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    private void runImport(Uri source, boolean folder, boolean includeBik, int startId) {
        boolean success = false;
        String error = "Import canceled.";
        try {
            File privateRoot = getFilesDir();
            File game = new File(privateRoot, "game");
            File previous = new File(privateRoot, "game.previous");
            if (previous.exists()) {
                throw new IOException("A previous copy is preserved. It will not be deleted automatically; resolve it before importing again.");
            }
            File stage = new File(privateRoot, "game.part");
            if (!stage.exists() && !stage.mkdirs()) throw new IOException("Could not create the private staging directory.");
            if (!stage.isDirectory()) throw new IOException("game.part exists but is not a directory.");

            Map<String, Long> sizes;
            if (folder) {
                List<SourceFile> files = scanFolder(source, includeBik);
                sizes = sizesOf(files);
                checkRequired(sizes.keySet());
                checkFreeSpace(bytesToWrite(sizes, stage), stage, game);
                totalBytes = sumSizes(sizes);
                copyFolder(files, stage);
            } else {
                // The first sequential pass determines uncompressed sizes before any output is written.
                sizes = preflightZip(source, includeBik);
                checkRequired(sizes.keySet());
                checkFreeSpace(bytesToWrite(sizes, stage), stage, game);
                totalBytes = sumSizes(sizes);
                extractZip(source, stage, includeBik, sizes);
            }

            validateStagedGame(stage, sizes);
            writeReadyMarker(stage, sizes);
            if (!validateInstalledGame(stage)) throw new IOException("Staged game data failed size or SHA-256 validation.");
            commitStage(stage, new File(privateRoot, "game"));
            success = validateInstalledGame(new File(privateRoot, "game"));
            if (!success) throw new IOException("The copied game data failed final validation.");
            error = "Import completed; required game files are valid.";
        } catch (Exception exception) {
            error = timedOut ? "Android stopped the import after its time limit. Start the import again to continue."
                    : (exception.getMessage() == null ? exception.toString() : exception.getMessage());
        } finally {
            sendProgress(error, true, success);
            releaseWakeLock();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf(startId);
        }
    }

    private Map<String, Long> preflightZip(Uri uri, boolean includeBik) throws IOException {
        Map<String, Long> sizes = new HashMap<>();
        try (ZipArchiveInputStream zip = openZip(uri)) {
            ZipArchiveEntry entry;
            byte[] buffer = new byte[BUFFER_SIZE];
            int entries = 0;
            long expandedTotal = 0;
            while ((entry = zip.getNextZipEntry()) != null) {
                throwIfCancelled();
                if (++entries > MAX_TREE_NODES) throw new IOException("The ZIP contains too many entries.");
                String relative = normalizedGamePath(entry.getName());
                boolean keep = shouldKeep(relative, entry.isDirectory(), includeBik);
                long bytes = 0;
                int count;
                while ((count = zip.read(buffer)) != -1) {
                    throwIfCancelled();
                    expandedTotal += count;
                    if (expandedTotal > MAX_GAME_BYTES) throw new IOException("The expanded ZIP exceeds the 20 GB safety limit.");
                    if (keep) bytes += count;
                }
                if (keep && !entry.isDirectory()) {
                    Long declared = entry.getSize() >= 0 ? entry.getSize() : null;
                    long measured = declared == null ? bytes : declared;
                    if (declared != null && bytes != declared) throw new IOException("ZIP size mismatch: " + relative);
                    putUniqueSize(sizes, relative, measured);
                }
                if (sumSizes(sizes) > MAX_GAME_BYTES) throw new IOException("Game data exceeds the 20 GB limit.");
            }
        } catch (IllegalArgumentException exception) {
            throw new IOException("Invalid or unsupported ZIP: " + exception.getMessage(), exception);
        }
        return sizes;
    }

    private void extractZip(Uri uri, File stage, boolean includeBik, Map<String, Long> expected) throws IOException {
        Map<String, Long> seen = new HashMap<>();
        try (ZipArchiveInputStream zip = openZip(uri)) {
            ZipArchiveEntry entry;
            byte[] buffer = new byte[BUFFER_SIZE];
            long expandedTotal = 0;
            while ((entry = zip.getNextZipEntry()) != null) {
                throwIfCancelled();
                String relative = normalizedGamePath(entry.getName());
                if (entry.isDirectory()) continue;
                if (!shouldKeep(relative, false, includeBik)) {
                    int skipped;
                    while ((skipped = zip.read(buffer)) != -1) {
                        throwIfCancelled();
                        expandedTotal += skipped;
                        if (expandedTotal > MAX_GAME_BYTES) throw new IOException("The expanded ZIP exceeds the 20 GB safety limit.");
                    }
                    continue;
                }
                Long expectedSize = expected.get(relative);
                if (expectedSize == null) throw new IOException("The ZIP changed between preflight and extraction.");
                File target = safeOutput(stage, relative);
                if (!target.getParentFile().isDirectory() && !target.getParentFile().mkdirs()) {
                    throw new IOException("Could not create a game-data directory.");
                }
                File temp = new File(target.getPath() + ".copying");
                MessageDigest digest = "default.xex".equals(new File(relative).getName()) ? sha256() : null;
                long count = 0;
                boolean skipWrite = target.isFile() && target.length() == expectedSize
                        && !"default.xex".equals(new File(relative).getName());
                try (OutputStreamWithDigest output = skipWrite ? null : new OutputStreamWithDigest(temp, digest)) {
                    int read;
                    while ((read = zip.read(buffer)) != -1) {
                        throwIfCancelled();
                        count += read;
                        expandedTotal += read;
                        copiedBytes += read;
                        if (count > MAX_GAME_BYTES || expandedTotal > MAX_GAME_BYTES) {
                            throw new IOException("The expanded ZIP exceeds the 20 GB safety limit.");
                        }
                        if (!skipWrite) output.write(buffer, 0, read);
                        if ((copiedBytes & ((4 * 1024 * 1024) - 1)) < read) sendProgress("Copying game data", false, false);
                    }
                }
                if (count != expectedSize) throw new IOException("File size mismatch: " + relative);
                if ("default.xex".equals(new File(relative).getName())) {
                    byte[] sourceHash = digest.digest();
                    byte[] targetHash = sha256File(skipWrite ? target : temp);
                    if (!MessageDigest.isEqual(sourceHash, targetHash)) {
                        if (skipWrite) {
                            // Same size but different XEX: rewrite this entry in a separate pass is unsafe for a stream.
                            throw new IOException("default.xex already exists with the same size but a different hash. Remove game.part before importing again.");
                        }
                        throw new IOException("default.xex SHA-256 changed during copying.");
                    }
                }
                if (!skipWrite) moveFile(temp, target);
                seen.put(relative, count);
            }
        }
        for (String required : REQUIRED) if (!seen.containsKey(required) && !new File(stage, required).isFile()) {
            throw new IOException("Required file is missing: " + required + " no ZIP.");
        }
    }

    private void copyFolder(List<SourceFile> files, File stage) throws IOException {
        byte[] buffer = new byte[BUFFER_SIZE];
        for (SourceFile source : files) {
            throwIfCancelled();
            File target = safeOutput(stage, source.relativePath);
            File parent = target.getParentFile();
            if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("Could not create a game-data directory.");
            MessageDigest sourceDigest = "default.xex".equals(source.relativePath) ? sha256() : null;
            boolean skipWrite = target.isFile() && source.size >= 0 && target.length() == source.size
                    && sourceDigest == null;
            File temp = new File(target.getPath() + ".copying");
            long count = 0;
            try (InputStream input = resolver().openInputStream(source.uri);
                 OutputStreamWithDigest output = skipWrite ? null : new OutputStreamWithDigest(temp, sourceDigest)) {
                if (input == null) throw new IOException("Could not open " + source.relativePath);
                int read;
                while ((read = input.read(buffer)) != -1) {
                    throwIfCancelled();
                    count += read; copiedBytes += read;
                    if (count > MAX_GAME_BYTES || copiedBytes > MAX_GAME_BYTES) throw new IOException("Game data exceeds the 20 GB limit.");
                    if (!skipWrite) output.write(buffer, 0, read);
                    if ((copiedBytes & ((4 * 1024 * 1024) - 1)) < read) sendProgress("Copying game data", false, false);
                }
            }
            if (source.size >= 0 && count != source.size) throw new IOException("File size mismatch: " + source.relativePath);
            if (sourceDigest != null) {
                byte[] sourceHash = sourceDigest.digest();
                byte[] targetHash = sha256File(skipWrite ? target : temp);
                if (!MessageDigest.isEqual(sourceHash, targetHash)) throw new IOException("default.xex SHA-256 changed during copying.");
            }
            if (!skipWrite) moveFile(temp, target);
            if (count > 0) sendProgress("Copying game data", false, false);
        }
    }

    private List<SourceFile> scanFolder(Uri tree, boolean includeBik) throws IOException {
        Uri gameRoot = findGameRoot(tree);
        if (gameRoot == null) throw new IOException("The selected folder does not contain all five required files in one directory.");
        List<SourceFile> result = new ArrayList<>();
        scanChildren(gameRoot, "", includeBik, result, 0, new int[] {0});
        return result;
    }

    private void scanChildren(Uri parent, String prefix, boolean includeBik,
                              List<SourceFile> result, int depth, int[] visited) throws IOException {
        if (depth > MAX_TREE_DEPTH) throw new IOException("The selected folder is nested too deeply.");
        for (Node node : children(parent)) {
            throwIfCancelled();
            if (++visited[0] > MAX_TREE_NODES) throw new IOException("The selected folder contains too many items.");
            String relative = prefix.isEmpty() ? node.name : prefix + "/" + node.name;
            if (node.directory) {
                if (includeBik) scanChildren(node.uri, relative, true, result, depth + 1, visited);
                continue;
            }
            String safe = normalizedGamePath(relative);
            if (!shouldKeep(safe, false, includeBik)) continue;
            result.add(new SourceFile(node.uri, safe, node.size));
            if (result.size() > MAX_TREE_NODES) throw new IOException("The selected folder contains too many items.");
        }
    }

    private Uri findGameRoot(Uri tree) throws IOException {
        List<Uri> pending = new ArrayList<>(); pending.add(tree);
        int visited = 0;
        for (int index = 0; index < pending.size() && visited < MAX_TREE_NODES; index++) {
            Uri directory = pending.get(index); visited++;
            List<Node> nodes = children(directory);
            Set<String> names = new HashSet<>();
            for (Node node : nodes) if (!node.directory) names.add(node.name);
            if (names.containsAll(REQUIRED_SET)) return directory;
            if (index == 0) {
                for (Node node : nodes) if (node.directory && node.name.equalsIgnoreCase("game")) pending.add(1, node.uri);
            }
            if (pending.size() < MAX_TREE_NODES) for (Node node : nodes) {
                if (node.directory && !node.name.equalsIgnoreCase("Android")) pending.add(node.uri);
            }
        }
        return null;
    }

    private List<Node> children(Uri treeOrDocument) throws IOException {
        String documentId;
        String encoded = treeOrDocument.toString();
        try {
            documentId = encoded.contains("/document/")
                    ? DocumentsContract.getDocumentId(treeOrDocument)
                    : DocumentsContract.getTreeDocumentId(treeOrDocument);
        } catch (IllegalArgumentException exception) {
            throw new IOException("Invalid SAF folder URI.", exception);
        }
        Uri childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeOrDocument, documentId);
        List<Node> result = new ArrayList<>();
        String[] columns = {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE,
                DocumentsContract.Document.COLUMN_SIZE};
        try (Cursor cursor = resolver().query(childrenUri, columns, null, null, null)) {
            if (cursor == null) throw new IOException("The document provider cannot list this folder.");
            int idCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int mimeCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_MIME_TYPE);
            int sizeCol = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_SIZE);
            while (cursor.moveToNext()) {
                String id = cursor.getString(idCol); String name = cursor.getString(nameCol);
                String mime = cursor.getString(mimeCol);
                long size = sizeCol >= 0 && !cursor.isNull(sizeCol) ? cursor.getLong(sizeCol) : -1L;
                Uri uri = DocumentsContract.buildDocumentUriUsingTree(treeOrDocument, id);
                result.add(new Node(uri, name, DocumentsContract.Document.MIME_TYPE_DIR.equals(mime), size));
            }
        } catch (SecurityException exception) {
            throw new IOException("Access to the selected folder expired. Select it again.", exception);
        }
        return result;
    }

    private void checkFreeSpace(long requiredBytes, File stage, File game) throws IOException {
        if (requiredBytes <= 0 || requiredBytes > MAX_GAME_BYTES) throw new IOException("Invalid total game-data size.");
        long total = stage.getTotalSpace();
        long free = stage.getUsableSpace();
        long reserve = Math.max(MIN_FREE_RESERVE, requiredBytes / 20);
        long stageAlreadyAllocated = directoryBytes(stage);
        long currentGameBytes = directoryBytes(game);
        // Usable space is already net of both directories. Keep both figures in
        // the estimate: the current game remains in place while game.part grows;
        // commitStage renames it to game.previous without making another copy.
        long retainedBytes = checkedAdd(stageAlreadyAllocated, currentGameBytes);
        long additionalBytes = checkedAdd(requiredBytes, reserve);
        if (free <= 0 || !ImportSpaceBudget.fits(total, free, retainedBytes, additionalBytes)) {
            throw new IOException("Not enough free storage. About "
                    + formatBytes(additionalBytes) + " more is required. The import keeps "
                    + formatBytes(retainedBytes) + " across game.part and game while copying.");
        }
    }

    private void throwIfCancelled() throws IOException {
        if (cancelled) {
            throw new IOException(timedOut
                    ? "Android stopped the import after its time limit. Start the import again to continue."
                    : "Import interrupted.");
        }
    }

    private static long directoryBytes(File root) throws IOException {
        if (!root.exists()) return 0;
        if (root.isFile()) return root.length();
        File[] children = root.listFiles();
        if (children == null) throw new IOException("Could not measure storage used by " + root.getName() + ".");
        long total = 0;
        for (File child : children) total = checkedAdd(total, directoryBytes(child));
        return total;
    }

    private static long checkedAdd(long left, long right) throws IOException {
        if (left < 0 || right < 0 || right > Long.MAX_VALUE - left) {
            throw new IOException("Invalid total game-data size.");
        }
        return left + right;
    }

    private static long bytesToWrite(Map<String, Long> sizes, File stage) throws IOException {
        long total = sumSizes(sizes);
        for (Map.Entry<String, Long> entry : sizes.entrySet()) {
            if ("default.xex".equals(entry.getKey())) continue;
            File existing = safeOutput(stage, entry.getKey());
            if (existing.isFile() && existing.length() == entry.getValue()) total -= entry.getValue();
        }
        return total;
    }

    private void validateStagedGame(File stage, Map<String, Long> expected) throws IOException {
        for (String name : REQUIRED) {
            File file = new File(stage, name);
            Long expectedSize = expected.get(name);
            if (!file.isFile() || file.length() <= 0 || expectedSize == null || file.length() != expectedSize) {
                throw new IOException("Required file is missing or incomplete: " + name);
            }
        }
        File xex = new File(stage, "default.xex");
        if (sha256File(xex).length != 32) throw new IOException("Could not validate default.xex SHA-256.");
    }

    static boolean validateInstalledGame(File game) {
        if (!game.isDirectory() || !new File(game, READY_MARKER).isFile()) return false;
        for (String name : REQUIRED) {
            File file = new File(game, name);
            if (!file.isFile() || file.length() <= 0) return false;
        }
        try {
            File marker = new File(game, READY_MARKER);
            java.util.Properties metadata = new java.util.Properties();
            try (InputStream input = new FileInputStream(marker)) { metadata.load(input); }
            for (String name : REQUIRED) {
                File file = new File(game, name);
                if (Long.parseLong(metadata.getProperty(name + ".size", "-1")) != file.length()) return false;
            }
            String expected = metadata.getProperty("default.xex.sha256", "");
            return expected.equals(hex(sha256File(new File(game, "default.xex"))));
        } catch (Exception exception) { return false; }
    }

    private void writeReadyMarker(File stage, Map<String, Long> sizes) throws IOException {
        String hash = hex(sha256File(new File(stage, "default.xex")));
        File marker = new File(stage, READY_MARKER);
        try (FileOutputStream output = new FileOutputStream(marker, false)) {
            StringBuilder metadata = new StringBuilder("default.xex.sha256=").append(hash).append('\n');
            for (String name : REQUIRED) metadata.append(name).append(".size=").append(sizes.get(name)).append('\n');
            output.write(metadata.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
            output.getFD().sync();
        }
    }

    private void commitStage(File stage, File game) throws IOException {
        File previous = new File(getFilesDir(), "game.previous");
        if (previous.exists()) throw new IOException("A previous copy is preserved in game.previous. It will not be removed automatically.");
        if (game.exists() && !game.renameTo(previous)) throw new IOException("Could not preserve the existing game directory.");
        if (!stage.renameTo(game)) {
            if (previous.exists()) previous.renameTo(game);
            throw new IOException("Could not promote game.part to game.");
        }
    }

    private static Map<String, Long> sizesOf(List<SourceFile> files) throws IOException {
        Map<String, Long> result = new HashMap<>();
        for (SourceFile source : files) {
            if (source.size < 0) throw new IOException("The provider did not report the size of " + source.relativePath + "; try another file picker.");
            putUniqueSize(result, source.relativePath, source.size);
        }
        return result;
    }

    private static long sumSizes(Map<String, Long> sizes) throws IOException {
        long total = 0;
        for (long size : sizes.values()) {
            if (size < 0 || size > MAX_GAME_BYTES - total) throw new IOException("Total size exceeds the 20 GB limit.");
            total += size;
        }
        return total;
    }

    private static void checkRequired(Set<String> paths) throws IOException {
        for (String required : REQUIRED) if (!paths.contains(required)) throw new IOException("Required file is missing: " + required + " in the selected game data.");
    }

    private static void putUniqueSize(Map<String, Long> map, String path, long size) throws IOException {
        Long old = map.put(path, size);
        if (old != null) throw new IOException("Duplicate file entry: " + path);
    }

    private static boolean shouldKeep(String path, boolean directory, boolean includeBik) {
        if (directory || path.isEmpty()) return false;
        if (REQUIRED_SET.contains(path)) return true;
        return includeBik && path.toLowerCase(Locale.ROOT).endsWith(".bik");
    }

    private static String normalizedGamePath(String original) throws IOException {
        if (original == null || original.isEmpty()) return "";
        String path = original.replace('\\', '/');
        if (path.startsWith("/") || path.matches("^[A-Za-z]:.*")) throw new IOException("The ZIP contains an absolute path: " + original);
        StringBuilder normalized = new StringBuilder();
        for (String part : path.split("/")) {
            if (part.isEmpty() || part.equals(".")) continue;
            if (part.equals("..") || part.indexOf('\0') >= 0) throw new IOException("The ZIP contains an unsafe path.");
            if (normalized.length() > 0) normalized.append('/');
            normalized.append(part);
        }
        path = normalized.toString();
        int marker = path.lastIndexOf("/game/");
        if (marker >= 0) path = path.substring(marker + 6);
        else if (path.startsWith("game/")) path = path.substring(5);
        return path;
    }

    private static File safeOutput(File root, String relative) throws IOException {
        File target = new File(root, relative);
        String canonicalRoot = root.getCanonicalPath();
        String canonicalTarget = target.getCanonicalPath();
        if (!canonicalTarget.startsWith(canonicalRoot + File.separator)) throw new IOException("Output path is outside the private game directory.");
        return target;
    }

    private static void moveFile(File from, File to) throws IOException {
        if (to.exists() && !to.delete()) throw new IOException("Could not replace " + to.getName());
        if (!from.renameTo(to)) throw new IOException("Could not finalize " + to.getName());
    }

    private static MessageDigest sha256() throws IOException {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException exception) { throw new IOException("SHA-256 is unavailable.", exception); }
    }

    private static byte[] sha256File(File file) throws IOException {
        MessageDigest digest = sha256(); byte[] buffer = new byte[BUFFER_SIZE];
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            int count; while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        return digest.digest();
    }

    private static String hex(byte[] data) {
        StringBuilder result = new StringBuilder(data.length * 2);
        for (byte value : data) result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return result.toString();
    }

    private ContentResolver resolver() { return getContentResolver(); }

    private ZipArchiveInputStream openZip(Uri uri) throws IOException {
        InputStream input = resolver().openInputStream(uri);
        if (input == null) throw new IOException("The file picker did not provide a readable ZIP stream.");
        return new ZipArchiveInputStream(new BufferedInputStream(input), "UTF-8", true, true);
    }

    private void sendProgress(String message, boolean finished, boolean success) {
        progressMessage = message;
        Intent update = new Intent(ACTION_PROGRESS).setPackage(getPackageName())
                .putExtra(EXTRA_MESSAGE, message).putExtra(EXTRA_COPIED, copiedBytes)
                .putExtra(EXTRA_TOTAL, totalBytes).putExtra(EXTRA_FINISHED, finished)
                .putExtra(EXTRA_SUCCESS, success);
        sendBroadcast(update);
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) manager.notify(NOTIFICATION_ID, buildNotification(message, copiedBytes, totalBytes));
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "MCLA Import", NotificationManager.IMPORTANCE_LOW);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification(String message, long copied, long total) {
        Intent open = new Intent(this, DataSetupActivity.class);
        PendingIntent pending = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0));
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID) : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle("MCLA Recomp")
                .setContentText(message + " · " + formatBytes(copied) + (total > 0 ? " / " + formatBytes(total) : ""))
                .setOngoing(!message.startsWith("Import completed"))
                .setContentIntent(pending);
        if (total > 0) builder.setProgress(100, (int) Math.min(100, copied * 100 / total), false);
        else builder.setProgress(0, 0, true);
        return builder.build();
    }

    private void acquireWakeLock() {
        PowerManager manager = getSystemService(PowerManager.class);
        if (manager == null) return;
        wakeLock = manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "mcla:asset-import");
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire(6L * 60L * 60L * 1000L);
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        wakeLock = null;
    }

    private static String formatBytes(long bytes) {
        return String.format(Locale.ROOT, "%.2f GB", bytes / (1024.0 * 1024.0 * 1024.0));
    }

    private static final class Node {
        final Uri uri; final String name; final boolean directory; final long size;
        Node(Uri uri, String name, boolean directory, long size) { this.uri = uri; this.name = name; this.directory = directory; this.size = size; }
    }

    private static final class SourceFile {
        final Uri uri; final String relativePath; final long size;
        SourceFile(Uri uri, String relativePath, long size) { this.uri = uri; this.relativePath = relativePath; this.size = size; }
    }

    private static final class OutputStreamWithDigest extends BufferedOutputStream {
        private final MessageDigest digest;
        OutputStreamWithDigest(File file, MessageDigest digest) throws IOException {
            super(new FileOutputStream(file, false), BUFFER_SIZE); this.digest = digest;
        }
        @Override public void write(byte[] data, int offset, int length) throws IOException {
            super.write(data, offset, length);
            if (digest != null) digest.update(data, offset, length);
        }
        @Override public void write(int value) throws IOException {
            super.write(value); if (digest != null) digest.update((byte) value);
        }
    }
}
