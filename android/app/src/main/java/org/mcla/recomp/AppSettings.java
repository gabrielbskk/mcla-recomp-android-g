package org.mcla.recomp;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Android launcher view of the same cvars stored in the runtime's mcla.toml. */
public final class AppSettings {
    public final String resolution;
    public final int fpsLimit;
    public final boolean vsync;
    public final String effects;
    public final boolean fpsCounter;
    public final boolean performanceLogging;

    private static final String[] CONFIG_KEYS = {
            "mcla_resolution", "video_mode_width", "video_mode_height", "mcla_fps",
            "vsync", "mcla_graphics_preset", "mcla_fps_counter", "mcla_perf_logging"
    };
    private static final String[] PRESET_DETAIL_KEYS = {
            "mcla_shadows", "mcla_race_shadows", "mcla_fast_car_shadows",
            "mcla_foliage_shadows", "mcla_city_lod", "mcla_traffic_lod",
            "mcla_traffic_distance", "mcla_pedestrians", "mcla_parked_cars",
            "mcla_foliage_impostors", "mcla_fullscreen_blur", "mcla_msaa",
            "mcla_motion_blur", "mcla_depth_of_field"
    };

    private AppSettings(String resolution, int fpsLimit, boolean vsync, String effects,
                        boolean fpsCounter, boolean performanceLogging) {
        this.resolution = resolution;
        this.fpsLimit = fpsLimit;
        this.vsync = vsync;
        this.effects = effects;
        this.fpsCounter = fpsCounter;
        this.performanceLogging = performanceLogging;
    }

    public static AppSettings defaults() {
        return new AppSettings("540p", 30, false, "performance", true, false);
    }

    public static AppSettings fromValues(Map<String, String> values, AppSettings fallback) {
        if (fallback == null) fallback = defaults();
        if (values == null) values = new HashMap<>();
        String resolution = parseResolution(values.get("resolution"), fallback.resolution);
        int fps = parseFps(values.get("fps_limit"), fallback.fpsLimit);
        boolean vsync = parseBoolean(values.get("vsync"), fallback.vsync);
        String effects = parseEffects(values.get("effects"), fallback.effects);
        boolean counter = parseBoolean(values.get("fps_counter"), fallback.fpsCounter);
        boolean logging = parseBoolean(values.get("performance_logging"), fallback.performanceLogging);
        return new AppSettings(resolution, fps, vsync, effects, counter, logging);
    }

    public static AppSettings load(File config) {
        Map<String, String> values = new HashMap<>();
        if (config != null && config.isFile()) {
            try (BufferedReader reader = new BufferedReader(new FileReader(config))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    int equals = line.indexOf('=');
                    if (equals < 0) continue;
                    String key = line.substring(0, equals).trim();
                    if (!isManagedKey(key)) continue;
                    String value = line.substring(equals + 1).trim();
                    if (value.length() >= 2 && value.startsWith("\"") && value.endsWith("\"")) {
                        value = value.substring(1, value.length() - 1);
                    }
                    values.put(key, value);
                }
            } catch (IOException ignored) {
                // A missing or unreadable config is treated like a fresh install.
            }
        }
        AppSettings defaults = defaults();
        return new AppSettings(
                parseResolution(values.get("mcla_resolution"), defaults.resolution),
                parseFps(values.get("mcla_fps"), defaults.fpsLimit),
                parseBoolean(values.get("vsync"), defaults.vsync),
                parseEffects(values.get("mcla_graphics_preset"), defaults.effects),
                parseBoolean(values.get("mcla_fps_counter"), defaults.fpsCounter),
                parseBoolean(values.get("mcla_perf_logging"), defaults.performanceLogging));
    }

    public void save(File config) throws IOException {
        File parent = config.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IOException("Cannot create settings directory");
        }
        List<String> kept = new ArrayList<>();
        String previousPreset = null;
        if (config.isFile()) {
            List<String> original = new ArrayList<>();
            try (BufferedReader reader = new BufferedReader(new FileReader(config))) {
                String line;
                while ((line = reader.readLine()) != null) original.add(line);
            }
            for (String line : original) {
                int equals = line.indexOf('=');
                if (equals >= 0 && "mcla_graphics_preset".equals(line.substring(0, equals).trim())) {
                    previousPreset = unquote(line.substring(equals + 1).trim());
                }
            }
            for (String line : original) {
                int equals = line.indexOf('=');
                if (equals >= 0) {
                    String key = line.substring(0, equals).trim();
                    if (isManagedKey(key)) continue;
                    if (!effects.equals(previousPreset) && isPresetDetailKey(key)) continue;
                }
                kept.add(line);
            }
        }
        List<String> settingsLines = new ArrayList<>();
        settingsLines.add("mcla_resolution = \"" + resolution + "\"");
        settingsLines.add("video_mode_width = " + widthFor(resolution));
        settingsLines.add("video_mode_height = " + heightFor(resolution));
        settingsLines.add("mcla_fps = " + fpsLimit);
        settingsLines.add("vsync = " + vsync);
        settingsLines.add("mcla_graphics_preset = \"" + effects + "\"");
        settingsLines.add("mcla_fps_counter = " + fpsCounter);
        settingsLines.add("mcla_perf_logging = " + performanceLogging);
        int insertAt = kept.size();
        for (int i = 0; i < kept.size(); i++) {
            if (kept.get(i).trim().startsWith("[")) { insertAt = i; break; }
        }
        kept.addAll(insertAt, settingsLines);

        File temporary = new File(config.getPath() + ".tmp");
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write("# Android launcher settings; consumed by ReXGlue cvars\n".getBytes(StandardCharsets.UTF_8));
            for (String line : kept) output.write((line + "\n").getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        }
        try {
            Files.move(temporary.toPath(), config.toPath(), StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException atomicMoveFailure) {
            try {
                Files.move(temporary.toPath(), config.toPath(), StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException moveFailure) {
                moveFailure.addSuppressed(atomicMoveFailure);
                temporary.delete();
                throw moveFailure;
            }
        }
    }

    public static String parseResolution(String value, String fallback) {
        if ("540p".equals(value) || "720p".equals(value) || "1080p".equals(value)) return value;
        return fallback;
    }

    public static int parseFps(String value, int fallback) {
        if (value == null) return fallback;
        try {
            int fps = Integer.parseInt(value.trim());
            return fps == -1 || fps == 0 || fps == 30 || fps == 60 || fps == 120 || fps == 240
                    ? fps : fallback;
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    public static boolean parseBoolean(String value, boolean fallback) {
        if ("true".equalsIgnoreCase(value)) return true;
        if ("false".equalsIgnoreCase(value)) return false;
        return fallback;
    }

    public static String parseEffects(String value, String fallback) {
        if ("low".equals(value) || "performance".equals(value)) return "performance";
        if ("medium".equals(value) || "balanced".equals(value)) return "balanced";
        if ("high".equals(value) || "original".equals(value)) return "original";
        return fallback;
    }

    public static int widthFor(String resolution) {
        if ("1080p".equals(resolution)) return 1920;
        if ("720p".equals(resolution)) return 1280;
        return 960;
    }

    public static int heightFor(String resolution) {
        if ("1080p".equals(resolution)) return 1080;
        if ("720p".equals(resolution)) return 720;
        return 540;
    }

    private static boolean isManagedKey(String key) {
        for (String managed : CONFIG_KEYS) if (managed.equals(key)) return true;
        return false;
    }

    private static boolean isPresetDetailKey(String key) {
        for (String detail : PRESET_DETAIL_KEYS) if (detail.equals(key)) return true;
        return false;
    }

    private static String unquote(String value) {
        return value.length() >= 2 && value.startsWith("\"") && value.endsWith("\"")
                ? value.substring(1, value.length() - 1) : value;
    }

    public boolean sameValues(AppSettings other) {
        return other != null && resolution.equals(other.resolution) && fpsLimit == other.fpsLimit
                && vsync == other.vsync && effects.equals(other.effects)
                && fpsCounter == other.fpsCounter && performanceLogging == other.performanceLogging;
    }
}
