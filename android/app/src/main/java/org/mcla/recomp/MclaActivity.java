package org.mcla.recomp;

import android.content.Intent;
import android.os.Bundle;

import java.util.HashMap;
import java.util.Map;

import org.libsdl.app.SDLActivity;

/** SDL native gameplay activity. Assets are already imported into app-private filesDir/game. */
public final class MclaActivity extends SDLActivity {
    @Override protected String[] getLibraries() {
        return new String[] { "main" };
    }

    @Override protected String[] getArguments() {
        Intent intent = getIntent();
        Bundle extras = intent == null ? null : intent.getExtras();
        if (extras == null) return new String[0];

        Map<String, String> values = new HashMap<>();
        copyExtra(extras, values, "resolution");
        copyExtra(extras, values, "fps_limit");
        copyExtra(extras, values, "vsync");
        copyExtra(extras, values, "effects");
        copyExtra(extras, values, "fps_counter");
        copyExtra(extras, values, "performance_logging");
        AppSettings defaults = AppSettings.defaults();
        AppSettings overrides = AppSettings.fromValues(values, defaults);
        java.util.ArrayList<String> args = new java.util.ArrayList<>();

        if (values.containsKey("resolution")) {
            args.add("--mcla_resolution=" + overrides.resolution);
            args.add("--video_mode_width=" + AppSettings.widthFor(overrides.resolution));
            args.add("--video_mode_height=" + AppSettings.heightFor(overrides.resolution));
        }
        if (values.containsKey("fps_limit")) args.add("--mcla_fps=" + overrides.fpsLimit);
        if (values.containsKey("vsync")) args.add(booleanFlag("vsync", overrides.vsync));
        if (values.containsKey("effects")) {
            args.add("--mcla_graphics_preset=" + overrides.effects);
            appendPresetArgs(args, overrides.effects);
        }
        if (values.containsKey("fps_counter")) {
            args.add(booleanFlag("mcla_fps_counter", overrides.fpsCounter));
        }
        if (values.containsKey("performance_logging")) {
            args.add(booleanFlag("mcla_perf_logging", overrides.performanceLogging));
        }
        return args.toArray(new String[0]);
    }

    private static void copyExtra(Bundle extras, Map<String, String> values, String key) {
        if (!extras.containsKey(key)) return;
        Object value = extras.get(key);
        if (value != null) values.put(key, String.valueOf(value));
    }

    private static String booleanFlag(String name, boolean enabled) {
        return enabled ? "--" + name : "--no-" + name;
    }

    private static void appendPresetArgs(java.util.List<String> args, String preset) {
        boolean performance = "performance".equals(preset);
        boolean balanced = "balanced".equals(preset);
        String quality = performance ? "0.25" : balanced ? "0.75" : "1.0";
        String density = performance ? "0.0" : balanced ? "0.75" : "1.0";
        String traffic = performance ? "100" : balanced ? "325" : "400";
        addBool(args, "mcla_shadows", !performance);
        addBool(args, "mcla_race_shadows", !performance);
        addBool(args, "mcla_fast_car_shadows", performance);
        addBool(args, "mcla_foliage_shadows", !performance && !balanced);
        addValue(args, "mcla_city_lod", quality);
        addValue(args, "mcla_traffic_lod", quality);
        addValue(args, "mcla_traffic_distance", traffic);
        addValue(args, "mcla_pedestrians", density);
        addValue(args, "mcla_parked_cars", density);
        addBool(args, "mcla_foliage_impostors", true);
        addBool(args, "mcla_fullscreen_blur", !performance);
        addBool(args, "mcla_msaa", !performance && !balanced);
        addBool(args, "mcla_motion_blur", !performance);
        addBool(args, "mcla_depth_of_field", !performance);
    }

    private static void addBool(java.util.List<String> args, String name, boolean value) {
        args.add(booleanFlag(name, value));
    }

    private static void addValue(java.util.List<String> args, String name, String value) {
        args.add("--" + name + "=" + value);
    }
}
