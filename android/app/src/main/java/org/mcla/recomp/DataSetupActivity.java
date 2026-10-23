package org.mcla.recomp;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Prepares optional XAPK/OBB data before SDL starts the native game. */
public final class DataSetupActivity extends Activity {
    private static final int REQUEST_STORAGE = 4301;
    private static final String PREFS = "mcla_xapk_setup";
    private static final String PREF_EXTRACTION_IN_PROGRESS = "obb_extraction_in_progress";
    private static final String READY_MARKER = ".mcla_obb_ready";
    private static final long MAX_OBB_BYTES = 20L * 1024L * 1024L * 1024L;

    private TextView status;
    private ProgressBar progress;
    private Button action;
    private boolean extracting;
    private boolean launching;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        DiagnosticsExporter.exportPreviousSession(this);
        buildSetupScreen();
        action.setOnClickListener(view -> requestAccessOrPrepare());
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!extracting && !launching) {
            prepareGameData();
        }
    }

    private void buildSetupScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_VERTICAL);
        int padding = dp(28);
        root.setPadding(padding, padding, padding, padding);
        root.setBackgroundColor(Color.rgb(16, 21, 29));

        TextView title = new TextView(this);
        title.setText("MCLA Recomp");
        title.setTextColor(Color.WHITE);
        title.setTextSize(26);
        root.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        status = new TextView(this);
        status.setTextColor(Color.rgb(218, 224, 235));
        status.setTextSize(16);
        status.setText("Conferindo os dados do jogo…");
        LinearLayout.LayoutParams statusParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        statusParams.topMargin = dp(20);
        root.addView(status, statusParams);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(ProgressBar.GONE);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(10));
        progressParams.topMargin = dp(18);
        root.addView(progress, progressParams);

        action = new Button(this);
        action.setText("Tentar novamente");
        LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        actionParams.topMargin = dp(18);
        root.addView(action, actionParams);

        setContentView(root);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void requestAccessOrPrepare() {
        if (hasStorageAccess()) {
            prepareGameData();
        } else if (Build.VERSION.SDK_INT >= 30) {
            showStatus("Permita o acesso a todos os arquivos para preparar os dados em /MLR.");
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            try {
                startActivity(intent);
            } catch (RuntimeException exception) {
                startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
            }
        } else {
            requestPermissions(new String[] {
                    Manifest.permission.READ_EXTERNAL_STORAGE,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE
            }, REQUEST_STORAGE);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_STORAGE) {
            if (hasStorageAccess()) {
                prepareGameData();
            } else {
                showAccessRequired();
            }
        }
    }

    private boolean hasStorageAccess() {
        if (Build.VERSION.SDK_INT >= 30) {
            return Environment.isExternalStorageManager();
        }
        return checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
    }

    private void showAccessRequired() {
        showStatus("Para ler ou extrair os dados do jogo, permita acesso a todos os arquivos. Depois toque em Tentar novamente.");
        action.setText("Permitir acesso aos arquivos");
        action.setEnabled(true);
    }

    private void prepareGameData() {
        if (extracting || launching) return;

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        boolean interrupted = prefs.getBoolean(PREF_EXTRACTION_IN_PROGRESS, false);
        File appGame = appGameDirectory();
        boolean appGameReady = isCompleteGame(appGame)
                && (!interrupted || new File(appGame, READY_MARKER).isFile());
        if (appGameReady) {
            prefs.edit().putBoolean(PREF_EXTRACTION_IN_PROGRESS, false).apply();
            launchGame();
            return;
        }

        File obb = findExpansionFile();
        if (obb != null) {
            extractExpansionFile(obb, appGame);
            return;
        }

        if (!hasStorageAccess()) {
            showAccessRequired();
            return;
        }
        File existingGame = findCompleteSharedGame();
        if (existingGame != null) {
            launchGame();
            return;
        }

        showStatus("Dados não encontrados. Coloque o jogo completo em /storage/emulated/0/MLR/game e tente novamente.");
        progress.setVisibility(ProgressBar.GONE);
        action.setText("Verificar novamente");
        action.setEnabled(true);
    }

    private File appGameDirectory() {
        File appFiles = getExternalFilesDir(null);
        if (appFiles != null) return new File(appFiles, "game");
        return new File(getFilesDir(), "game");
    }

    private File findCompleteSharedGame() {
        File shared = Environment.getExternalStorageDirectory();
        File[] candidates = {
                new File(shared, "MLR/game"),
                new File(shared, "MLR")
        };
        for (File candidate : candidates) {
            if (isCompleteGame(candidate)) return candidate;
        }
        return null;
    }

    private boolean isCompleteGame(File root) {
        String[] required = {
                "default.xex", "xarchive_cache.rpf", "xarchive_audio.rpf",
                "xarchive_audlo.rpf", "xarchive_music.rpf"
        };
        for (String name : required) {
            File file = new File(root, name);
            if (!file.isFile() || file.length() == 0) return false;
        }
        return true;
    }

    private File findExpansionFile() {
        File obbDirectory = getObbDir();
        if (obbDirectory == null) {
            obbDirectory = new File(Environment.getExternalStorageDirectory(),
                    "Android/obb/" + getPackageName());
        }
        long versionCode;
        try {
            PackageManager packageManager = getPackageManager();
            android.content.pm.PackageInfo packageInfo =
                    packageManager.getPackageInfo(getPackageName(), 0);
            versionCode = Build.VERSION.SDK_INT >= 28
                    ? packageInfo.getLongVersionCode()
                    : packageInfo.versionCode;
        } catch (PackageManager.NameNotFoundException exception) {
            versionCode = 1;
        }

        String packageName = getPackageName();
        String[] supportedVersions = {Long.toString(versionCode), "2", "1"};
        for (String supportedVersion : supportedVersions) {
            File candidate = new File(obbDirectory,
                    "main." + supportedVersion + "." + packageName + ".obb");
            if (candidate.isFile()) return candidate;
        }
        return null;
    }

    private void extractExpansionFile(File obb, File destination) {
        extracting = true;
        action.setEnabled(false);
        action.setText("Preparando…");
        progress.setVisibility(ProgressBar.VISIBLE);
        progress.setIndeterminate(true);
        showStatus("Lendo o pacote de dados. A primeira preparação pode levar alguns minutos.");

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (!prefs.edit().putBoolean(PREF_EXTRACTION_IN_PROGRESS, true).commit()) {
            extractionFailed("Não consegui salvar o estado da preparação. Tente novamente.");
            return;
        }

        new Thread(() -> {
            try {
                long totalBytes = extractZip(obb, destination);
                if (!isCompleteGame(destination)) {
                    throw new IOException("O pacote terminou, mas faltam arquivos principais do jogo.");
                }
                File marker = new File(destination, READY_MARKER);
                try (FileOutputStream output = new FileOutputStream(marker)) {
                    output.write("ready".getBytes(StandardCharsets.UTF_8));
                }
                if (!prefs.edit().putBoolean(PREF_EXTRACTION_IN_PROGRESS, false).commit()) {
                    throw new IOException("Não consegui confirmar a preparação dos dados.");
                }
                runOnUiThread(() -> {
                    extracting = false;
                    progress.setIndeterminate(false);
                    progress.setProgress(100);
                    showStatus("Dados prontos (" + formatBytes(totalBytes) + "). Abrindo o jogo…");
                    launchGame();
                });
            } catch (Exception exception) {
                extractionFailed(exception.getMessage() == null ? exception.toString() : exception.getMessage());
            }
        }, "mcla-obb-extract").start();
    }

    private long extractZip(File archive, File destination) throws IOException {
        if (!destination.exists() && !destination.mkdirs()) {
            throw new IOException("Não consegui criar " + destination.getAbsolutePath());
        }
        String canonicalRoot = destination.getCanonicalPath();
        long copiedBytes = 0;
        long totalBytes = 0;
        int lastProgress = -1;
        byte[] buffer = new byte[256 * 1024];

        try (ZipFile zip = new ZipFile(archive)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (!entry.isDirectory() && entry.getSize() > 0) {
                    if (entry.getSize() > MAX_OBB_BYTES - totalBytes) {
                        throw new IOException("Os dados passam do limite de 20 GB.");
                    }
                    totalBytes += entry.getSize();
                }
            }
            if (totalBytes <= 0 || totalBytes > MAX_OBB_BYTES) {
                throw new IOException("Tamanho dos dados inválido ou acima do limite de 20 GB.");
            }
            long freeBytes = destination.getFreeSpace();
            if (freeBytes > 0 && freeBytes < totalBytes + 256L * 1024L * 1024L) {
                throw new IOException("Não há espaço livre suficiente para extrair os dados do jogo.");
            }

            entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String relative = entry.getName().replace('\\', '/');
                while (relative.startsWith("./")) relative = relative.substring(2);
                if (relative.startsWith("game/")) relative = relative.substring("game/".length());
                if (relative.isEmpty()) continue;
                if (relative.startsWith("/") || relative.matches("^[A-Za-z]:.*")) {
                    throw new IOException("Caminho inválido no pacote de dados.");
                }

                File outputFile = new File(destination, relative);
                String canonicalOutput = outputFile.getCanonicalPath();
                if (!canonicalOutput.equals(canonicalRoot)
                        && !canonicalOutput.startsWith(canonicalRoot + File.separator)) {
                    throw new IOException("O pacote tentou gravar fora da pasta do jogo.");
                }
                if (entry.isDirectory()) {
                    if (!outputFile.isDirectory() && !outputFile.mkdirs()) {
                        throw new IOException("Não consegui criar uma pasta dos dados do jogo.");
                    }
                    continue;
                }

                File parent = outputFile.getParentFile();
                if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
                    throw new IOException("Não consegui criar uma pasta dos dados do jogo.");
                }
                try (InputStream input = new BufferedInputStream(zip.getInputStream(entry));
                     BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(outputFile))) {
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        output.write(buffer, 0, count);
                        copiedBytes += count;
                    }
                }

                int currentProgress = (int) Math.min(100, copiedBytes * 100 / totalBytes);
                if (currentProgress != lastProgress) {
                    lastProgress = currentProgress;
                    final int progressValue = currentProgress;
                    final long copiedValue = copiedBytes;
                    runOnUiThread(() -> {
                        progress.setIndeterminate(false);
                        progress.setProgress(progressValue);
                        showStatus("Extraindo dados do jogo: " + progressValue + "% (" + formatBytes(copiedValue) + ").");
                    });
                }
            }
        }
        return copiedBytes;
    }

    private void extractionFailed(String message) {
        runOnUiThread(() -> {
            extracting = false;
            progress.setIndeterminate(false);
            showStatus("Não consegui preparar os dados: " + message);
            action.setText("Tentar novamente");
            action.setEnabled(true);
        });
    }

    private void showStatus(String text) {
        status.setText(text);
    }

    private String formatBytes(long bytes) {
        return String.format(java.util.Locale.ROOT, "%.1f GB", bytes / (1024.0 * 1024.0 * 1024.0));
    }

    private void launchGame() {
        if (launching) return;
        launching = true;
        action.setEnabled(false);
        action.setText("Preparando…");
        progress.setVisibility(ProgressBar.VISIBLE);
        progress.setIndeterminate(true);
        showStatus("Identificando a GPU e preparando o driver gráfico…");
        Context appContext = getApplicationContext();
        new Thread(() -> {
            GpuDriverManager.Selection selection = GpuDriverManager.prepare(appContext);
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                progress.setVisibility(ProgressBar.GONE);
                showStatus(selection.message + " Abrindo o jogo…");
                try {
                    startActivity(new Intent(this, MclaActivity.class));
                    finish();
                } catch (RuntimeException exception) {
                    launching = false;
                    action.setEnabled(true);
                    action.setText("Tentar novamente");
                    showStatus("Não consegui abrir o jogo: " + exception.getMessage());
                }
            });
        }, "mcla-gpu-driver-prepare").start();
    }
}
