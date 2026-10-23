package org.mcla.recomp;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.widget.Toast;

import org.libsdl.app.SDLActivity;

public final class MclaActivity extends SDLActivity {
    private static final int REQUEST_NOTIFICATIONS = 4101;
    private static final int REQUEST_STORAGE = 4102;

    @Override
    protected String[] getLibraries() {
        return new String[] { "main" };
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestNeededAccess();
    }

    private void requestNeededAccess() {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] { Manifest.permission.POST_NOTIFICATIONS }, REQUEST_NOTIFICATIONS);
            return;
        }
        if (Build.VERSION.SDK_INT < 30 && !hasAppOwnedGameData() &&
                checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] {
                    Manifest.permission.READ_EXTERNAL_STORAGE,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE
            }, REQUEST_STORAGE);
            return;
        }
        if (!hasAppOwnedGameData()) requestAllFilesAccess();
    }

    private boolean hasAppOwnedGameData() {
        java.io.File externalFiles = getExternalFilesDir(null);
        java.io.File[] roots = {
                externalFiles == null ? null : new java.io.File(externalFiles, "game"),
                new java.io.File(getFilesDir(), "game")
        };
        String[] required = {
                "default.xex", "xarchive_cache.rpf", "xarchive_audio.rpf",
                "xarchive_audlo.rpf", "xarchive_music.rpf"
        };
        for (java.io.File root : roots) {
            if (root == null) continue;
            boolean complete = true;
            for (String name : required) {
                java.io.File file = new java.io.File(root, name);
                if (!file.isFile() || file.length() == 0) {
                    complete = false;
                    break;
                }
            }
            if (complete) return true;
        }
        return false;
    }

    private void requestAllFilesAccess() {
        if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            Toast.makeText(this,
                    "Allow all-files access so MCLA Recomp can read game data from /MLR.",
                    Toast.LENGTH_LONG).show();
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_NOTIFICATIONS || requestCode == REQUEST_STORAGE) {
            requestAllFilesAccess();
        }
    }
}
