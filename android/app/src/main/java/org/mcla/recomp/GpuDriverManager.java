package org.mcla.recomp;

import android.content.Context;
import android.opengl.EGL14;
import android.opengl.EGLConfig;
import android.opengl.EGLContext;
import android.opengl.EGLDisplay;
import android.opengl.EGLSurface;
import android.opengl.GLES20;
import android.os.Build;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Chooses a bundled Vulkan driver for an exact supported GPU, otherwise the system driver. */
final class GpuDriverManager {
    private static final String TAG = "MCLA-GPU";
    private static final String ROOT = "gpu_drivers";
    private static final String SELECTED = "selected-driver.txt";
    private static final String FAILED_START = "custom-driver-starting";
    private static final long MAX_DRIVER_FILE = 200L * 1024L * 1024L;

    static final class Selection {
        final String id;
        final String renderer;
        final String message;

        Selection(String id, String renderer, String message) {
            this.id = id;
            this.renderer = renderer;
            this.message = message;
        }
    }

    private GpuDriverManager() {}

    static Selection prepare(Context context) {
        File root = new File(context.getFilesDir(), ROOT);
        if (!root.isDirectory() && !root.mkdirs()) {
            return selectSystem(context, "Could not prepare the driver directory.");
        }

        File failedStart = new File(root, FAILED_START);
        if (failedStart.isFile()) {
            failedStart.delete();
            return selectSystem(context, "The alternate driver failed last session; using the system driver.");
        }

        String renderer = detectGlRenderer();
        String normalized = renderer.toLowerCase(Locale.ROOT);
        String profile = null;
        String asset = null;
        String library = null;
        if (normalized.contains("adreno") && normalized.contains("740")) {
            profile = "turnip-adreno740";
            asset = "gpu_drivers/turnip-adreno740.zip";
            library = "libvulkan_freedreno.so";
        } else if (Build.VERSION.SDK_INT >= 30 && normalized.contains("mali-g52")) {
            profile = "panvk-mali-g52";
            asset = "gpu_drivers/panvk-mali-g52.zip";
            library = "libvulkan_panfrost.so";
        }

        if (profile == null) {
            return selectSystem(context, "No validated alternate profile for this GPU.", renderer);
        }

        File driverDirectory = new File(root, profile);
        File driverLibrary = new File(driverDirectory, library);
        if (!driverLibrary.isFile() || driverLibrary.length() == 0) {
            try {
                extractDriver(context, asset, driverDirectory, library, profile);
            } catch (Exception exception) {
                Log.w(TAG, "Could not prepare " + profile + "; using system Vulkan", exception);
                return selectSystem(context, "Alternate driver unavailable; using the system driver.", renderer);
            }
        }

        if (!driverLibrary.isFile() || driverLibrary.length() == 0) {
            return selectSystem(context, "Alternate driver is incomplete; using the system driver.", renderer);
        }

        writeSelection(context, profile);
        return new Selection(profile, renderer, "Selected driver profile: " + profile + ".");
    }

    private static Selection selectSystem(Context context, String message) {
        return selectSystem(context, message, "unavailable");
    }

    private static Selection selectSystem(Context context, String message, String renderer) {
        writeSelection(context, "system");
        return new Selection("system", renderer, message);
    }

    private static void writeSelection(Context context, String profile) {
        File root = new File(context.getFilesDir(), ROOT);
        File selected = new File(root, SELECTED);
        File temporary = new File(root, SELECTED + ".tmp");
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write((profile + "\n").getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
            if (!temporary.renameTo(selected)) {
                try (FileOutputStream direct = new FileOutputStream(selected)) {
                    direct.write((profile + "\n").getBytes(StandardCharsets.UTF_8));
                    direct.getFD().sync();
                }
                temporary.delete();
            }
        } catch (IOException exception) {
            Log.w(TAG, "Could not persist GPU selection", exception);
        }
    }

    private static void extractDriver(Context context, String assetName, File target,
                                      String expectedLibrary, String profile) throws Exception {
        File root = target.getParentFile();
        File temporary = new File(root, profile + ".tmp");
        deleteTree(temporary);
        if (!temporary.mkdirs()) throw new IOException("Cannot create temporary driver directory");

        boolean foundLibrary = false;
        long expandedBytes = 0;
        try (InputStream source = context.getAssets().open(assetName);
             ZipInputStream zip = new ZipInputStream(source)) {
            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                String name = entry.getName();
                if (entry.isDirectory() || name.isEmpty() || name.contains("/") || name.contains("\\")
                        || name.equals(".") || name.equals("..")) {
                    throw new IOException("Unexpected path in bundled driver archive");
                }
                if (!(name.equals(expectedLibrary) || name.equals("meta.json")
                        || name.equals("libc++_shared.so") || name.equals("libdrm.so"))) {
                    throw new IOException("Unexpected file in bundled driver archive: " + name);
                }

                File outputFile = new File(temporary, name);
                try (BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(outputFile))) {
                    int count;
                    while ((count = zip.read(buffer)) != -1) {
                        expandedBytes += count;
                        if (expandedBytes > MAX_DRIVER_FILE) throw new IOException("Driver archive is too large");
                        output.write(buffer, 0, count);
                    }
                }
                if (name.equals(expectedLibrary)) foundLibrary = true;
                zip.closeEntry();
            }
        }
        if (!foundLibrary) throw new IOException("Expected Vulkan driver library is missing");

        File metadata = new File(temporary, "meta.json");
        if (metadata.isFile()) {
            byte[] bytes = new byte[(int) metadata.length()];
            try (InputStream input = context.getAssets().open(assetName);
                 ZipInputStream zip = new ZipInputStream(input)) {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    if (entry.getName().equals("meta.json")) {
                        int offset = 0;
                        while (offset < bytes.length) {
                            int count = zip.read(bytes, offset, bytes.length - offset);
                            if (count < 0) break;
                            offset += count;
                        }
                        break;
                    }
                }
            }
            JSONObject json = new JSONObject(new String(bytes, StandardCharsets.UTF_8));
            if (!expectedLibrary.equals(json.optString("libraryName"))) {
                throw new IOException("Driver metadata names a different library");
            }
            if (Build.VERSION.SDK_INT < json.optInt("minApi", 1)) {
                throw new IOException("This driver requires a newer Android version");
            }
        }

        deleteTree(target);
        if (!temporary.renameTo(target)) throw new IOException("Could not activate extracted driver");
    }

    private static void deleteTree(File file) {
        if (file == null || !file.exists()) return;
        File[] children = file.listFiles();
        if (children != null) for (File child : children) deleteTree(child);
        file.delete();
    }

    private static String detectGlRenderer() {
        EGLDisplay display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
        if (display == null || display == EGL14.EGL_NO_DISPLAY) return "";
        int[] version = new int[2];
        if (!EGL14.eglInitialize(display, version, 0, version, 1)) return "";

        EGLContext context = EGL14.EGL_NO_CONTEXT;
        EGLSurface surface = EGL14.EGL_NO_SURFACE;
        String renderer = "";
        try {
            int[] configAttributes = {
                    EGL14.EGL_RENDERABLE_TYPE, 4, // EGL_OPENGL_ES2_BIT
                    EGL14.EGL_SURFACE_TYPE, EGL14.EGL_PBUFFER_BIT,
                    EGL14.EGL_RED_SIZE, 8,
                    EGL14.EGL_GREEN_SIZE, 8,
                    EGL14.EGL_BLUE_SIZE, 8,
                    EGL14.EGL_NONE
            };
            EGLConfig[] configs = new EGLConfig[1];
            int[] configCount = new int[1];
            if (!EGL14.eglChooseConfig(display, configAttributes, 0, configs, 0, 1, configCount, 0)
                    || configCount[0] == 0) return "";

            int[] contextAttributes = {EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE};
            context = EGL14.eglCreateContext(display, configs[0], EGL14.EGL_NO_CONTEXT,
                    contextAttributes, 0);
            int[] surfaceAttributes = {EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE};
            surface = EGL14.eglCreatePbufferSurface(display, configs[0], surfaceAttributes, 0);
            if (context == null || context == EGL14.EGL_NO_CONTEXT
                    || surface == null || surface == EGL14.EGL_NO_SURFACE
                    || !EGL14.eglMakeCurrent(display, surface, surface, context)) return "";

            String value = GLES20.glGetString(GLES20.GL_RENDERER);
            renderer = value == null ? "" : value;
        } catch (RuntimeException exception) {
            Log.w(TAG, "GPU identification failed; using system Vulkan", exception);
        } finally {
            EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE,
                    EGL14.EGL_NO_CONTEXT);
            if (surface != null && surface != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(display, surface);
            if (context != null && context != EGL14.EGL_NO_CONTEXT) EGL14.eglDestroyContext(display, context);
            EGL14.eglTerminate(display);
        }
        return renderer;
    }
}
