import java.util.HashMap;
import java.util.Map;
import java.io.File;
import java.io.FileWriter;
import org.mcla.recomp.AppSettings;

public final class AndroidSettingsTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        AppSettings defaults = AppSettings.defaults();
        check(defaults.fpsCounter, "FPS counter must default to enabled");
        check(!defaults.performanceLogging, "performance logging must default to disabled");
        check("540p".equals(defaults.resolution), "resolution default must be 540p");
        check("medium".equals(defaults.effects), "graphics preset must default to medium");

        Map<String, String> valid = new HashMap<>();
        valid.put("resolution", "720p");
        valid.put("fps_limit", "0");
        valid.put("vsync", "false");
        valid.put("effects", "low");
        valid.put("fps_counter", "true");
        valid.put("performance_logging", "true");
        AppSettings parsed = AppSettings.fromValues(valid, defaults);
        check("720p".equals(parsed.resolution), "resolution parse");
        check(parsed.fpsLimit == 0, "uncapped FPS parse");
        check(!parsed.vsync, "vsync parse");
        check("low".equals(parsed.effects), "low preset remains distinct from super low");
        check(parsed.fpsCounter && parsed.performanceLogging, "boolean parse");

        check("super_low".equals(AppSettings.parseEffects("performance", "medium")),
                "legacy performance preset maps to super low");
        check("medium".equals(AppSettings.parseEffects("balanced", "super_low")),
                "legacy balanced preset maps to medium");
        check("ultra".equals(AppSettings.parseEffects("original", "medium")),
                "legacy original preset maps to ultra");
        check("ultra".equals(AppSettings.parseEffects("ULTRA", "medium")),
                "preset parsing is case-insensitive");

        Map<String, String> invalid = new HashMap<>();
        invalid.put("resolution", "8k");
        invalid.put("fps_limit", "900");
        invalid.put("vsync", "maybe");
        invalid.put("effects", "cinematic");
        invalid.put("fps_counter", "not-bool");
        AppSettings rejected = AppSettings.fromValues(invalid, defaults);
        check("540p".equals(rejected.resolution), "invalid resolution falls back");
        check(rejected.fpsLimit == defaults.fpsLimit, "invalid FPS falls back");
        check(rejected.vsync == defaults.vsync, "invalid vsync falls back");
        check("medium".equals(rejected.effects), "invalid preset falls back to medium");
        check(rejected.fpsCounter, "invalid FPS counter retains enabled default");

        try {
            File config = File.createTempFile("mcla-settings-test", ".toml");
            try (FileWriter writer = new FileWriter(config)) {
                writer.write("unrelated_cvar = 7\nmcla_graphics_preset = \"original\"\n"
                        + "mcla_shadows = true\n[mcla_log]\nlevel = \"debug\"\n");
            }
            Map<String, String> persistedValues = new HashMap<>();
            persistedValues.put("resolution", "1080p");
            persistedValues.put("fps_limit", "60");
            persistedValues.put("vsync", "true");
            persistedValues.put("effects", "high");
            persistedValues.put("fps_counter", "false");
            persistedValues.put("performance_logging", "true");
            AppSettings saved = AppSettings.fromValues(persistedValues, defaults);
            saved.save(config);
            AppSettings restored = AppSettings.load(config);
            check("1080p".equals(restored.resolution), "saved resolution reloads");
            check(restored.fpsLimit == 60 && restored.vsync, "saved timing reloads");
            check("high".equals(restored.effects), "saved preset reloads");
            check(!restored.fpsCounter && restored.performanceLogging, "saved toggles reload");
            String contents = new String(java.nio.file.Files.readAllBytes(config.toPath()),
                    java.nio.charset.StandardCharsets.UTF_8);
            check(contents.contains("unrelated_cvar = 7"), "unrelated cvars are preserved");
            check(contents.indexOf("mcla_resolution =") < contents.indexOf("[mcla_log]"),
                    "managed settings remain top-level TOML values");
            check(!contents.contains("mcla_shadows = true"),
                    "changing presets clears stale per-effect overrides");
            config.delete();
        } catch (Exception e) {
            throw new AssertionError("settings persistence test", e);
        }
        System.out.println("AndroidSettingsTest: PASS");
    }

}
