package org.mcla.recomp;

import android.app.Activity;
import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;

import java.io.File;
import java.util.Locale;

/** Launcher screen for importing game assets into app-private filesDir/game. */
public final class DataSetupActivity extends Activity {
    private static final int REQUEST_ZIP = 4301;
    private static final int REQUEST_FOLDER = 4302;
    private static final int REQUEST_ISO = 4303;
    private static final int REQUEST_LOG_FOLDER = 4304;
    private static final int REQUEST_NOTIFICATIONS = 4306;

    private TextView status;
    private ProgressBar progress;
    private Button play;
    private Button importZip;
    private Button importFolder;
    private CheckBox includeVideos;
    private AppSettings appSettings;
    private File settingsFile;
    private boolean importing;
    private boolean testLaunchStarted;
    private PendingImport pendingImport;

    private static final class PendingImport {
        final Uri uri;
        final boolean folder;
        final boolean videos;
        PendingImport(Uri uri, boolean folder, boolean videos) {
            this.uri = uri; this.folder = folder; this.videos = videos;
        }
    }

    private final BroadcastReceiver importReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (intent == null) return;
            String message = intent.getStringExtra(DataImportService.EXTRA_MESSAGE);
            long copied = intent.getLongExtra(DataImportService.EXTRA_COPIED, 0L);
            long total = intent.getLongExtra(DataImportService.EXTRA_TOTAL, 0L);
            if (total > 0) {
                progress.setIndeterminate(false);
                progress.setProgress((int) Math.min(100L, copied * 100L / total));
            }
            if (message != null) showStatus(message + "  " + formatBytes(copied)
                    + (total > 0 ? " / " + formatBytes(total) : " copiados"));
            if (intent.getBooleanExtra(DataImportService.EXTRA_FINISHED, false)) {
                importing = false;
                progress.setIndeterminate(false);
                progress.setVisibility(ProgressBar.GONE);
                setImportButtonsEnabled(true);
                if (intent.getBooleanExtra(DataImportService.EXTRA_SUCCESS, false)) {
                    showStatus("Dados importados e validados. Toque em Jogar.");
                    play.setEnabled(true);
                } else {
                    showStatus("Importação não concluída: " + (message == null ? "erro desconhecido" : message));
                    refreshReadiness();
                }
            }
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        settingsFile = new File(new File(getFilesDir(), "mcla-recomp/userdata"), "mcla.toml");
        appSettings = AppSettings.load(settingsFile);
        buildScreen();
        DiagnosticsExporter.exportPreviousSession(this);
        refreshReadiness();
    }

    @Override protected void onStart() {
        super.onStart();
        IntentFilter filter = new IntentFilter(DataImportService.ACTION_PROGRESS);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(importReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(importReceiver, filter);
    }

    @Override protected void onResume() {
        super.onResume();
        if (play != null && !importing) refreshReadiness();
    }

    @Override protected void onStop() {
        try { unregisterReceiver(importReceiver); } catch (IllegalArgumentException ignored) { }
        super.onStop();
    }

    private void buildScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_VERTICAL);
        int pad = dp(28);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(16, 21, 29));

        TextView title = new TextView(this);
        title.setText("MCLA Recomp"); title.setTextColor(Color.WHITE); title.setTextSize(26);
        root.addView(title, matchWrap());
        status = new TextView(this);
        status.setTextColor(Color.rgb(218, 224, 235)); status.setTextSize(16);
        status.setText("Escolha os arquivos do jogo para importar.");
        LinearLayout.LayoutParams statusLp = matchWrap(); statusLp.topMargin = dp(16);
        root.addView(status, statusLp);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100); progress.setVisibility(ProgressBar.GONE);
        LinearLayout.LayoutParams progressLp = new LinearLayout.LayoutParams(-1, dp(10));
        progressLp.topMargin = dp(14); root.addView(progress, progressLp);

        TextView settingsTitle = new TextView(this);
        settingsTitle.setText("Configurações"); settingsTitle.setTextColor(Color.WHITE);
        settingsTitle.setTextSize(20);
        LinearLayout.LayoutParams settingsTitleLp = matchWrap(); settingsTitleLp.topMargin = dp(22);
        root.addView(settingsTitle, settingsTitleLp);
        addSpinnerSetting(root, "Resolução", new String[]{"540p", "720p", "1080p"},
                "540p".equals(appSettings.resolution) ? 0 : "720p".equals(appSettings.resolution) ? 1 : 2,
                index -> saveAppSetting("resolution", new String[]{"540p", "720p", "1080p"}[index]));
        addSpinnerSetting(root, "Limite de FPS", new String[]{"30 FPS", "60 FPS", "120 FPS", "Sem limite"},
                appSettings.fpsLimit == 0 ? 3 : appSettings.fpsLimit == 60 ? 1 : appSettings.fpsLimit == 120 ? 2 : 0,
                index -> saveAppSetting("fps_limit", new String[]{"30", "60", "120", "0"}[index]));
        addSwitchSetting(root, "V-Sync", appSettings.vsync,
                checked -> saveAppSetting("vsync", Boolean.toString(checked)));
        addSpinnerSetting(root, "Graphics preset", new String[]{"Super Low", "Low", "Medium", "High", "Ultra"},
                "super_low".equals(appSettings.effects) ? 0 : "low".equals(appSettings.effects) ? 1
                        : "medium".equals(appSettings.effects) ? 2 : "high".equals(appSettings.effects) ? 3 : 4,
                index -> saveAppSetting("effects", new String[]{"super_low", "low", "medium", "high", "ultra"}[index]));
        addSwitchSetting(root, "Contador de FPS (ligado por padrão)", appSettings.fpsCounter,
                checked -> saveAppSetting("fps_counter", Boolean.toString(checked)));
        addSwitchSetting(root, "Gravar log de desempenho", appSettings.performanceLogging,
                checked -> saveAppSetting("performance_logging", Boolean.toString(checked)));

        importZip = addButton(root, "Importar ZIP", view -> chooseZip());
        importFolder = addButton(root, "Importar pasta extraída", view -> chooseFolder());
        addButton(root, "Selecionar ISO", view -> chooseIso());
        includeVideos = new CheckBox(this);
        includeVideos.setText("Incluir vídeos .bik opcionais (pode ocupar bastante espaço)");
        includeVideos.setTextColor(Color.rgb(218, 224, 235));
        includeVideos.setChecked(false);
        root.addView(includeVideos, matchWrap());
        play = addButton(root, "Jogar", view -> launchGame(null));
        play.setEnabled(false);
        addButton(root, "Exportar logs", view -> exportLogs());
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(root);
        setContentView(scroll);
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private Button addButton(LinearLayout parent, String label, android.view.View.OnClickListener listener) {
        Button button = new Button(this); button.setText(label); button.setOnClickListener(listener);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2); lp.topMargin = dp(8);
        parent.addView(button, lp); return button;
    }

    private interface IndexChanged { void onChanged(int index); }
    private interface SwitchChanged { void onChanged(boolean checked); }

    private void addSpinnerSetting(LinearLayout parent, String label, String[] values,
                                   int selected, IndexChanged changed) {
        TextView title = new TextView(this);
        title.setText(label); title.setTextColor(Color.rgb(218, 224, 235)); title.setTextSize(15);
        LinearLayout.LayoutParams titleLp = matchWrap(); titleLp.topMargin = dp(8);
        parent.addView(title, titleLp);
        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        spinner.setSelection(selected, false);
        spinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> view,
                                                 android.view.View item, int position, long id) {
                changed.onChanged(position);
            }
            @Override public void onNothingSelected(android.widget.AdapterView<?> view) { }
        });
        parent.addView(spinner, matchWrap());
    }

    private void addSwitchSetting(LinearLayout parent, String label, boolean checked,
                                  SwitchChanged changed) {
        Switch toggle = new Switch(this);
        toggle.setText(label); toggle.setTextColor(Color.rgb(218, 224, 235));
        toggle.setChecked(checked);
        toggle.setOnCheckedChangeListener((button, value) -> changed.onChanged(value));
        LinearLayout.LayoutParams lp = matchWrap(); lp.topMargin = dp(4);
        parent.addView(toggle, lp);
    }

    private void saveAppSetting(String key, String value) {
        java.util.Map<String, String> values = new java.util.HashMap<>();
        values.put("resolution", appSettings.resolution);
        values.put("fps_limit", Integer.toString(appSettings.fpsLimit));
        values.put("vsync", Boolean.toString(appSettings.vsync));
        values.put("effects", appSettings.effects);
        values.put("fps_counter", Boolean.toString(appSettings.fpsCounter));
        values.put("performance_logging", Boolean.toString(appSettings.performanceLogging));
        values.put(key, value);
        AppSettings updated = AppSettings.fromValues(values, appSettings);
        if (updated.sameValues(appSettings)) return;
        try {
            updated.save(settingsFile);
            appSettings = updated;
        } catch (java.io.IOException error) {
            showStatus("Não foi possível salvar as configurações: " + error.getMessage());
        }
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private void chooseZip() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/zip");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_ZIP);
    }

    private void chooseFolder() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_FOLDER);
    }

    private void chooseIso() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType("*/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_ISO);
    }

    private void exportLogs() {
        Uri saved = DiagnosticsExporter.savedDestination(this);
        if (saved != null) {
            new Thread(() -> {
                String result = DiagnosticsExporter.exportToTree(this, saved);
                runOnUiThread(() -> showStatus(result));
            }, "mcla-log-export").start();
            return;
        }
        showStatus("Selecione Documents; os arquivos serão exportados para MCLA/logs.");
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_LOG_FOLDER);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();

        if (requestCode == REQUEST_ISO) {
            showStatus("ISO XGD não é extraída pelo app. Extraia a imagem no PC e depois escolha a pasta resultante.");
        } else if (requestCode == REQUEST_LOG_FOLDER) {
            try {
                int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                getContentResolver().takePersistableUriPermission(uri, flags);
            } catch (SecurityException ignored) { /* Export remains available for this session. */ }
            DiagnosticsExporter.rememberDestination(this, uri);
            new Thread(() -> {
                String result = DiagnosticsExporter.exportToTree(this, uri);
                runOnUiThread(() -> showStatus(result));
            }, "mcla-log-export").start();
        } else if (requestCode == REQUEST_ZIP || requestCode == REQUEST_FOLDER) {
            String name = displayName(uri);
            if (requestCode == REQUEST_ZIP && name.toLowerCase(Locale.ROOT).endsWith(".iso")) {
                showStatus("ISO XGD não é extraída pelo app. Extraia a imagem no PC e importe a pasta ou um ZIP.");
                return;
            }
            startImport(uri, requestCode == REQUEST_FOLDER, includeVideos.isChecked());
        }
    }

    private String displayName(Uri uri) {
        try (android.database.Cursor cursor = getContentResolver().query(uri,
                new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) return cursor.getString(0);
        } catch (Exception ignored) { }
        return uri.getLastPathSegment() == null ? "" : uri.getLastPathSegment();
    }

    private void startImport(Uri uri, boolean folder, boolean videos) {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            pendingImport = new PendingImport(uri, folder, videos);
            showStatus("Permita notificações para acompanhar o progresso. Se negar, a importação ainda poderá continuar.");
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQUEST_NOTIFICATIONS);
            return;
        }
        performImport(uri, folder, videos);
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_NOTIFICATIONS || pendingImport == null) return;
        PendingImport pending = pendingImport;
        pendingImport = null;
        performImport(pending.uri, pending.folder, pending.videos);
    }

    private void performImport(Uri uri, boolean folder, boolean videos) {
        importing = true; play.setEnabled(false); setImportButtonsEnabled(false);
        progress.setVisibility(ProgressBar.VISIBLE); progress.setIndeterminate(true);
        showStatus("Conferindo espaço e preparando a importação…");
        Intent service = new Intent(this, DataImportService.class)
                .setAction(folder ? DataImportService.ACTION_IMPORT_FOLDER : DataImportService.ACTION_IMPORT_ZIP)
                .setData(uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                .putExtra(DataImportService.EXTRA_INCLUDE_BIK, videos);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(service); else startService(service);
    }

    private void refreshReadiness() {
        play.setEnabled(false);
        new Thread(() -> {
            File game = new File(getFilesDir(), "game");
            boolean ready = DataImportService.validateInstalledGame(game);
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed() || importing) return;
                play.setEnabled(ready);
                showStatus(ready ? "Dados privados validados. Pronto para jogar." :
                        "Importe ZIP ou pasta extraída. O app usará uma cópia privada em filesDir/game.");
                if (ready && !testLaunchStarted && hasIntentOverrides(getIntent())) {
                    testLaunchStarted = true;
                    launchGame(getIntent());
                }
            });
        }, "mcla-game-validation").start();
    }

    private static boolean hasIntentOverrides(Intent intent) {
        if (intent == null || intent.getExtras() == null) return false;
        android.os.Bundle extras = intent.getExtras();
        return extras.containsKey("resolution") || extras.containsKey("fps_limit")
                || extras.containsKey("vsync") || extras.containsKey("effects")
                || extras.containsKey("fps_counter") || extras.containsKey("performance_logging");
    }

    private void launchGame(Intent overrides) {
        if (!play.isEnabled()) return;
        play.setEnabled(false);
        showStatus("Preparando a GPU…");
        new Thread(() -> {
            GpuDriverManager.Selection selection = GpuDriverManager.prepare(getApplicationContext());
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                try {
                    showStatus(selection.message + " Abrindo o jogo…");
                    Intent game = new Intent(this, MclaActivity.class);
                    if (overrides != null && overrides.getExtras() != null) {
                        game.putExtras(overrides.getExtras());
                    }
                    startActivity(game);
                    finish();
                } catch (RuntimeException exception) {
                    showStatus("Não consegui abrir o jogo: " + exception.getMessage());
                    refreshReadiness();
                }
            });
        }, "mcla-gpu-driver-prepare").start();
    }

    private void setImportButtonsEnabled(boolean enabled) {
        importZip.setEnabled(enabled); importFolder.setEnabled(enabled);
    }

    private void showStatus(String text) { status.setText(text); }

    private static String formatBytes(long bytes) {
        return String.format(Locale.ROOT, "%.2f GB", bytes / (1024.0 * 1024.0 * 1024.0));
    }
}
