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

}
