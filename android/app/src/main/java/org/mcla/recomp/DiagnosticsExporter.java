package org.mcla.recomp;

import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.provider.DocumentsContract;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Keeps logs private; the user explicitly chooses a SAF destination to export them. */
final class DiagnosticsExporter {
    private static final String PREFS = "mcla_diagnostics";
    private static final String DESTINATION = "export_tree_uri";
    private static final String LAST_EXIT_TIME = "last_exit_timestamp";
    private static final int MAX_TRACE_BYTES = 1024 * 1024;

    private DiagnosticsExporter() {}

    static Uri savedDestination(Context context) {
        String value = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(DESTINATION, null);
        return value == null ? null : Uri.parse(value);
    }

    static void rememberDestination(Context context, Uri uri) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(DESTINATION, uri.toString()).apply();
    }

    static void exportPreviousSession(Context context) {
        Uri destination = savedDestination(context);
        if (destination == null) return;
        new Thread(() -> exportToTree(context.getApplicationContext(), destination), "mcla-previous-log-export").start();
    }

    static String exportToTree(Context context, Uri treeUri) {
        try {
            List<File> logs = findLogs(context);
            Uri outputDirectory = resolveOutputDirectory(context, treeUri);
            for (File log : logs) {
                try (InputStream input = new BufferedInputStream(new FileInputStream(log))) {
                    writeDocument(context, treeUri, outputDirectory, "log-" + log.getName(), input);
                }
            }
            String report = buildReport(context, logs);
            writeDocument(context, treeUri, outputDirectory, "diagnostics-latest.txt",
                    new java.io.ByteArrayInputStream(report.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            return "Logs exportados para Documents/MCLA/logs (" + logs.size() + " arquivo(s)).";
        } catch (Exception exception) {
            String message = exception.getMessage();
            return "Não consegui exportar os logs: " + (message == null ? exception.toString() : message);
        }
    }

    private static List<File> findLogs(Context context) {
        File directory = new File(context.getFilesDir(), "mcla-recomp/logs");
        File[] files = directory.listFiles(file -> file.isFile() && file.getName().endsWith(".log"));
        List<File> result = new ArrayList<>();
        if (files != null) result.addAll(java.util.Arrays.asList(files));
        result.sort(Comparator.comparingLong(File::lastModified));
        if (result.size() > 3) return new ArrayList<>(result.subList(result.size() - 3, result.size()));
        return result;
    }

    private static String buildReport(Context context, List<File> logs) {
        String stamp = timestamp(System.currentTimeMillis());
        StringBuilder report = new StringBuilder(1024);
        report.append("MCLA Recomp diagnostics\n")
                .append("Exported: ").append(stamp).append('\n')
                .append("Device: ").append(Build.MANUFACTURER).append(' ').append(Build.MODEL).append('\n')
                .append("Android: ").append(Build.VERSION.RELEASE).append(" (SDK ").append(Build.VERSION.SDK_INT).append(")\n")
                .append("App: ").append(context.getPackageName()).append(' ').append(appVersion(context)).append('\n')
                .append("Private log folder: ").append(new File(context.getFilesDir(), "mcla-recomp/logs").getAbsolutePath()).append('\n')
                .append("Logs exported: ").append(logs.size()).append('\n');
        ApplicationExitInfo exit = findNewExit(context);
        if (exit != null) {
            report.append("Previous process exit: ").append(timestamp(exit.getTimestamp())).append('\n')
                    .append("Exit reason: ").append(exitReasonName(exit.getReason())).append(" (").append(exit.getReason()).append(")\n")
                    .append("Exit status: ").append(exit.getStatus()).append('\n')
                    .append("Importance: ").append(exit.getImportance()).append('\n');
            if (exit.getDescription() != null) report.append("Description: ").append(exit.getDescription()).append('\n');
            appendTrace(report, exit);
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                    .putLong(LAST_EXIT_TIME, exit.getTimestamp()).apply();
        } else {
            report.append("Previous process exit: no new Android exit record\n");
        }
        report.append("\nThe game reads assets and writes runtime logs only in app-private storage.\n");
        return report.toString();
    }

    private static Uri resolveOutputDirectory(Context context, Uri treeUri) throws Exception {
        String treeId = DocumentsContract.getTreeDocumentId(treeUri);
        Uri rootDocument = DocumentsContract.buildDocumentUriUsingTree(treeUri, treeId);
        String rootName = displayName(context, rootDocument);
        String currentId = treeId;
        if (!"logs".equalsIgnoreCase(rootName)) {
            currentId = findOrCreateDirectory(context, treeUri, currentId, "MCLA");
            currentId = findOrCreateDirectory(context, treeUri, currentId, "logs");
        }
        return DocumentsContract.buildDocumentUriUsingTree(treeUri, currentId);
    }

    private static String findOrCreateDirectory(Context context, Uri tree, String parentId, String name) throws Exception {
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
        String[] columns = {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (android.database.Cursor cursor = context.getContentResolver().query(children, columns, null, null, null)) {
            if (cursor != null) {
                int idCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
                int nameCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
                int mimeCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_MIME_TYPE);
                while (cursor.moveToNext()) {
                    if (name.equals(cursor.getString(nameCol))
                            && DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(mimeCol))) {
                        return cursor.getString(idCol);
                    }
                }
            }
        }
        Uri parent = DocumentsContract.buildDocumentUriUsingTree(tree, parentId);
        Uri created = DocumentsContract.createDocument(context.getContentResolver(), parent,
                DocumentsContract.Document.MIME_TYPE_DIR, name);
        if (created == null) throw new IOException("O provedor não criou a pasta " + name);
        return DocumentsContract.getDocumentId(created);
    }

    private static String displayName(Context context, Uri document) {
        try (android.database.Cursor cursor = context.getContentResolver().query(document,
                new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) return cursor.getString(0);
        } catch (Exception ignored) { }
        return "";
    }

    private static void writeDocument(Context context, Uri tree, Uri parent, String name, InputStream input) throws IOException {
        Uri existing = findChild(context, tree, parent, name);
        Uri outputUri = existing != null ? existing : DocumentsContract.createDocument(context.getContentResolver(), parent,
                "text/plain", name);
        if (outputUri == null) throw new IOException("Não consegui criar " + name);
        try (OutputStream output = context.getContentResolver().openOutputStream(outputUri, "wt")) {
            if (output == null) throw new IOException("Não consegui abrir " + name + " para escrita.");
            byte[] buffer = new byte[64 * 1024]; int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
        }
    }

    private static Uri findChild(Context context, Uri tree, Uri parent, String name) {
        String parentId = DocumentsContract.getDocumentId(parent);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
        try (android.database.Cursor cursor = context.getContentResolver().query(children,
                new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                        DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
            if (cursor == null) return null;
            int idCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameCol = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            while (cursor.moveToNext()) if (name.equals(cursor.getString(nameCol))) {
                return DocumentsContract.buildDocumentUriUsingTree(tree, cursor.getString(idCol));
            }
        } catch (Exception ignored) { }
        return null;
    }

    private static ApplicationExitInfo findNewExit(Context context) {
        if (Build.VERSION.SDK_INT < 30) return null;
        ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        if (manager == null) return null;
        List<ApplicationExitInfo> exits = manager.getHistoricalProcessExitReasons(context.getPackageName(), 0, 8);
        if (exits == null || exits.isEmpty()) return null;
        long lastSeen = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_EXIT_TIME, 0L);
        ApplicationExitInfo newest = exits.get(0);
        return newest.getTimestamp() > lastSeen ? newest : null;
    }

    private static void appendTrace(StringBuilder report, ApplicationExitInfo exit) {
        if (Build.VERSION.SDK_INT < 30) return;
        try (InputStream trace = exit.getTraceInputStream()) {
            if (trace == null) return;
            report.append("\nAndroid exit trace (up to 1 MiB):\n");
            byte[] buffer = new byte[8192]; int remaining = MAX_TRACE_BYTES;
            while (remaining > 0) {
                int count = trace.read(buffer, 0, Math.min(buffer.length, remaining));
                if (count < 0) break;
                report.append(new String(buffer, 0, count, java.nio.charset.StandardCharsets.UTF_8)); remaining -= count;
            }
        } catch (IOException ignored) { report.append("Android exit trace: unavailable\n"); }
    }

    private static String appVersion(Context context) {
        try {
            android.content.pm.PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
            return info.versionName + " (" + (Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode) + ")";
        } catch (android.content.pm.PackageManager.NameNotFoundException ignored) { return "unknown"; }
    }

    private static String exitReasonName(int reason) {
        switch (reason) {
            case 1: return "EXIT_SELF"; case 2: return "SIGNALED"; case 3: return "LOW_MEMORY";
            case 4: return "JAVA_CRASH"; case 5: return "NATIVE_CRASH"; case 6: return "ANR";
            case 7: return "INITIALIZATION_FAILURE"; case 8: return "PERMISSION_CHANGE";
            case 9: return "EXCESSIVE_RESOURCE_USAGE"; case 10: return "USER_REQUESTED";
            case 11: return "USER_STOPPED"; case 12: return "DEPENDENCY_DIED";
            case 13: return "OTHER"; case 14: return "FREEZER"; default: return "UNKNOWN";
        }
    }

    private static String timestamp(long value) {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(new Date(value));
    }
}
