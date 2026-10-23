package org.mcla.recomp;

import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Exports the previous game session's runtime logs and Android exit report. */
final class DiagnosticsExporter {
    private static final String PREFS = "mcla_diagnostics";
    private static final String LAST_EXIT_TIME = "last_exit_timestamp";
    private static final String DOCUMENT_DIRECTORY = "Documents/MCLA Recomp/";
    private static final int MAX_TRACE_BYTES = 1024 * 1024;

    private DiagnosticsExporter() {}

    static void exportPreviousSession(Context context) {
        try {
            List<File> logs = findLogs(context);
            ApplicationExitInfo exit = findNewExit(context);
            String stamp = timestamp(System.currentTimeMillis());

            for (File log : logs) {
                try (InputStream input = new BufferedInputStream(new FileInputStream(log))) {
                    writeDocument(context, "log-" + log.getName(), "text/plain", input);
                } catch (IOException ignored) {
                    // Keep exporting other logs if one rotated during the copy.
                }
            }

            StringBuilder report = new StringBuilder(1024);
            long exportedExitTimestamp = 0L;
            report.append("MCLA Recomp diagnostics\n")
                    .append("Exported: ").append(stamp).append('\n')
                    .append("Device: ").append(Build.MANUFACTURER).append(' ').append(Build.MODEL).append('\n')
                    .append("Android: ").append(Build.VERSION.RELEASE)
                    .append(" (SDK ").append(Build.VERSION.SDK_INT).append(")\n")
                    .append("App: ").append(context.getPackageName()).append(' ')
                    .append(appVersion(context)).append("\n")
                    .append("Runtime log folder: ").append(logDirectory(context).getAbsolutePath()).append('\n')
                    .append("Logs exported: ").append(logs.size()).append('\n');

            if (exit != null) {
                report.append("Previous process exit: ").append(timestamp(exit.getTimestamp())).append('\n')
                        .append("Exit reason: ").append(exitReasonName(exit.getReason()))
                        .append(" (").append(exit.getReason()).append(")\n")
                        .append("Exit status: ").append(exit.getStatus()).append('\n')
                        .append("Importance: ").append(exit.getImportance()).append('\n');
                if (exit.getDescription() != null) {
                    report.append("Description: ").append(exit.getDescription()).append('\n');
                }
                appendTrace(report, exit);
                exportedExitTimestamp = exit.getTimestamp();
            } else {
                report.append("Previous process exit: no new Android exit record\n");
            }
            report.append("\nRaw runtime logs are stored alongside this report.\n")
                    .append("Android exit records may identify a native crash, ANR, low-memory kill, or normal exit.\n");

            writeDocument(context, "diagnostics-latest.txt", "text/plain",
                    new java.io.ByteArrayInputStream(report.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            if (exportedExitTimestamp != 0L) {
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                        .putLong(LAST_EXIT_TIME, exportedExitTimestamp).apply();
            }
        } catch (Exception ignored) {
            // Diagnostics must never prevent the game launcher from starting.
        }
    }

    private static List<File> findLogs(Context context) {
        File directory = logDirectory(context);
        File[] files = directory.listFiles(file -> file.isFile() && file.getName().endsWith(".log"));
        List<File> result = new ArrayList<>();
        if (files != null) {
            Collections.addAll(result, files);
            result.sort(Comparator.comparingLong(File::lastModified));
        }
        return result;
    }

    private static File logDirectory(Context context) {
        File external = context.getExternalFilesDir(null);
        return new File(external != null ? external : context.getFilesDir(), "logs");
    }

    private static ApplicationExitInfo findNewExit(Context context) {
        if (Build.VERSION.SDK_INT < 30) return null;
        ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        if (manager == null) return null;
        List<ApplicationExitInfo> exits = manager.getHistoricalProcessExitReasons(context.getPackageName(), 0, 8);
        if (exits == null || exits.isEmpty()) return null;
        long lastSeen = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getLong(LAST_EXIT_TIME, 0L);
        ApplicationExitInfo newest = exits.get(0);
        return newest.getTimestamp() > lastSeen ? newest : null;
    }

    private static void appendTrace(StringBuilder report, ApplicationExitInfo exit) {
        if (Build.VERSION.SDK_INT < 30) return;
        try (InputStream trace = exit.getTraceInputStream()) {
            if (trace == null) return;
            report.append("\nAndroid exit trace (up to 1 MiB):\n");
            byte[] buffer = new byte[8192];
            int remaining = MAX_TRACE_BYTES;
            while (remaining > 0) {
                int count = trace.read(buffer, 0, Math.min(buffer.length, remaining));
                if (count < 0) break;
                report.append(new String(buffer, 0, count, java.nio.charset.StandardCharsets.UTF_8));
                remaining -= count;
            }
            report.append('\n');
        } catch (IOException ignored) {
            report.append("Android exit trace: unavailable\n");
        }
    }

    private static void writeDocument(Context context, String name, String mimeType, InputStream input)
            throws IOException {
        if (Build.VERSION.SDK_INT < 29) {
            File externalDocuments = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
            File documents = new File(externalDocuments != null ? externalDocuments : context.getFilesDir(), "MCLA Recomp");
            if (!documents.isDirectory() && !documents.mkdirs()) throw new IOException("Cannot create diagnostics folder");
            File output = new File(documents, name);
            try (OutputStream stream = new java.io.FileOutputStream(output)) {
                copy(input, stream);
            }
            return;
        }

        ContentResolver resolver = context.getContentResolver();
        Uri collection = MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        Uri document = findDocument(resolver, collection, name);
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        values.put(MediaStore.MediaColumns.MIME_TYPE, mimeType);
        values.put(MediaStore.MediaColumns.RELATIVE_PATH, DOCUMENT_DIRECTORY);
        values.put(MediaStore.MediaColumns.IS_PENDING, 1);
        if (document == null) document = resolver.insert(collection, values);
        else resolver.update(document, values, null, null);
        if (document == null) throw new IOException("Cannot create Documents entry");
        try (OutputStream stream = resolver.openOutputStream(document, "wt")) {
            if (stream == null) throw new IOException("Cannot open Documents entry");
            copy(input, stream);
        } finally {
            ContentValues ready = new ContentValues();
            ready.put(MediaStore.MediaColumns.IS_PENDING, 0);
            resolver.update(document, ready, null, null);
        }
    }

    private static Uri findDocument(ContentResolver resolver, Uri collection, String name) {
        String[] projection = {MediaStore.MediaColumns._ID};
        String selection = MediaStore.MediaColumns.DISPLAY_NAME + "=? AND "
                + MediaStore.MediaColumns.RELATIVE_PATH + "=?";
        try (Cursor cursor = resolver.query(collection, projection, selection,
                new String[] {name, DOCUMENT_DIRECTORY}, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                return Uri.withAppendedPath(collection,
                        Long.toString(cursor.getLong(cursor.getColumnIndexOrThrow(MediaStore.MediaColumns._ID))));
            }
        }
        return null;
    }

    private static void copy(InputStream input, OutputStream output) throws IOException {
        byte[] buffer = new byte[64 * 1024];
        int count;
        while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
    }

    private static String appVersion(Context context) {
        try {
            android.content.pm.PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
            return info.versionName + " (" + (Build.VERSION.SDK_INT >= 28
                    ? info.getLongVersionCode() : info.versionCode) + ")";
        } catch (android.content.pm.PackageManager.NameNotFoundException ignored) {
            return "unknown";
        }
    }

    private static String exitReasonName(int reason) {
        switch (reason) {
            case 1: return "EXIT_SELF";
            case 2: return "SIGNALED";
            case 3: return "LOW_MEMORY";
            case 4: return "JAVA_CRASH";
            case 5: return "NATIVE_CRASH";
            case 6: return "ANR";
            case 7: return "INITIALIZATION_FAILURE";
            case 8: return "PERMISSION_CHANGE";
            case 9: return "EXCESSIVE_RESOURCE_USAGE";
            case 10: return "USER_REQUESTED";
            case 11: return "USER_STOPPED";
            case 12: return "DEPENDENCY_DIED";
            case 13: return "OTHER";
            case 14: return "FREEZER";
            default: return "UNKNOWN";
        }
    }

    private static String timestamp(long value) {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(new Date(value));
    }
}
