# Auditoria completa do MCLA Android — código, build e runtime

## Identificação e escopo

- **Data:** 2026-10-26.
- **Checkout analisado:** `/data/data/com.termux/files/home/recomp-fix-mxcla-vkcache`.
- **Branch/commit:** `feature/android-vk-cache` / `430c9ce` (`fix(android): enforce 30fps cap and improve perf capture`).
- **Remote observado:** `git@github.com:gabrielbskk/recomp-fix-mxcla.git`. Não houve push; este remote não foi tratado como autorização para publicar.
- **Escopo:** 17.060 linhas em `src/`, `android/app/src/main/java/`, `scripts/` e `tests/`, além de `CMakeLists.txt`, `patches/`, manifesto, Gradle e documentação. Também foram revisados os históricos de build e os testes de Android.
- **Fora do escopo deliberadamente:** `game/`, `generated/`, `out/`, caches, submódulos não necessários à leitura, APKs, chaves, logs brutos e dados do jogo. Essas áreas são geradas ou contêm material que não deve entrar no repositório.

Esta rodada foi somente de auditoria e documentação. **Nenhuma fonte do renderer foi alterada, nenhum APK foi gerado e nenhuma instalação/limpeza de dados foi executada nesta rodada.**

## APK, dispositivo e pastas usados como evidência

O relatório usa o APK já existente, produzido anteriormente pelo processo manual ARM64 (não por Gradle):

- Arquivo local: `/data/data/com.termux/files/home/recomp-fix-mxcla-vkcache/out/apk/MCLA-v012-vkcache-renan-fixes-v6-30fps.apk`.
- SHA-256: `a3629b43a25063a5dfec80b5dc9a8890a7e97dfa3021d15e07fe92de4c637c1f`.
- Pacote/versão: `org.mcla.recomp.openbeta`, `0.1.2-experimental`, versionCode `3`.
- ABI: `arm64-v8a`; assinatura de teste verificada pelo certificado SHA-256 `c12a43023ed864654e56bed81d91e2d0fd98e46c5f22cbec32d5b585661ca7aa`.
- Dispositivo: Samsung SM-S911B, Android 16 (SDK 36), Snapdragon 8 Gen 2/Adreno 740.
- Dados lidos pelo runtime: `/data/data/org.mcla.recomp.openbeta/files/game`.
- Logs privados do runtime: `/data/user/0/org.mcla.recomp.openbeta/files/mcla-recomp/logs`.
- Exportação observada: `/storage/emulated/0/Documents/MCLA/logs`.

O endpoint ADB usado no teste não é repetido neste arquivo para não publicar um endereço de rede pessoal. Os artefatos completos continuam somente no aparelho/ambiente local.

## Comandos e resultados reproduzidos

1. `python3 -m unittest discover -s tests -p 'test_*.py' -q` — **59 testes passaram** em 26,482 s.
2. `cppcheck --enable=warning,performance,portability --inline-suppr --suppress=missingIncludeSystem --quiet --language=c++ src` — terminou sem erro fatal e emitiu apenas sete avisos de inicialização de membros, listados abaixo.
3. A construção anterior comprovada usou `JOBS=6 scripts/resume_android_termux_build.sh` para `mcla`, `rexruntime` e `rexgpu-xenos`, seguida de `scripts/assemble_android_apk.sh` com `AAPT2=/data/data/com.termux/files/usr/bin/aapt2`, alinhamento, assinatura e `apksigner`. **Não repeti o build agora**, conforme a instrução de não gerar APK.
4. `git status --short` estava limpo antes desta documentação. O relatório está sendo adicionado como documentação force-added porque a regra genérica `/docs/*.md` do `.gitignore` o exclui por padrão.

Avisos do `cppcheck`:

- `src/settings_menu.cpp:387-390`: membros agregados de `ItemDef` sem inicializador explícito.
- `src/touch_controls.cpp:48,51,53`: campos `TouchLayout::stick_radius`, `pedal_radius` e `face_radius` sem inicializador explícito.

Não há evidência de uso de lixo nesses dois casos: `TouchLayout` é criado com `{}` em `src/touch_controls.cpp:64`, e `ItemDef` é usado como agregado estático. Ainda assim, inicializadores explícitos deixariam o contrato mais claro.

## Estado comprovado por logs

| Área | Evidência | Conclusão |
| --- | --- | --- |
| Memória guest | O log registra `ASharedMemory_create`, `bytes=4831842304`, `errno=0 (Success)`, nove views mapeadas e avanço de `Runtime::Setup`. | A regressão de reserva de 4 GiB/4,5 GiB não reproduziu nesta build. |
| Vulkan | O runtime abriu `Adreno (TM) 740`, API Vulkan `1.3.128`, driver Qualcomm proprietário. | O caminho Vulkan do sistema inicializou; não prova desempenho ideal. |
| Cache de pipelines | O log carregou `10.776.549` bytes e salvou o cache; a sessão registrou 189 pipelines e `461.478 us` de criação acumulada. | A persistência está ativa e é observável. Isso não prova que seja o único gargalo. |
| Estabilidade | Não apareceu `FATAL EXCEPTION`, SIGSEGV ou exceção MCLA no trecho fresco. O encerramento posterior foi `ActivityManager ... remove task`, após a tarefa ser fechada. | Esta execução chegou a funcionar; não é uma certificação de ausência de todos os crashes. |
| Gamepad | O SDL detectou `PS4 Controller` (VID `054C`, PID `05C4`) e também `MCLA Touch Controls`. | A descoberta do dispositivo funciona; mapeamento de ações dentro do jogo ainda não foi provado. |
| Assets | Um rastreio chegou à seleção de carros após falhar ao abrir dois `.loc`; a evidência disponível registrou tentativa de `intro720.bik`, sem tentativa de `nxeart` ou `root_directory_padding.pad`. | `.bik` não pode ser declarado dispensável globalmente. O rastreio de uma cena não fecha a lista de assets. |
| Logs públicos | `diagnostics-latest.txt` informa dispositivo, versão, pasta privada e ausência de novo registro de saída Android. | A exportação funciona sem depender de ADB para ler o relatório resumido. |

## Medição de desempenho disponível

Os dados existentes **não são um benchmark controlado de FPS de tela**:

- O CSV `log-performance-v3-e818dee25daa74d5.csv` contém múltiplas sessões no mesmo arquivo e apresenta valores como `771`, `713` e até `1264` `presented_fps`. Também há primeira amostra com somente uma apresentação e janela curta.
- Em outra sessão, o log do runtime registrou `game-frame` de `29,8 ticks/s` e depois `6,1`, `1,7`, `1,5` e `2,8 ticks/s`, com p95 entre aproximadamente `35,84 ms` e `997,45 ms`. Esses ticks são do temporizador do jogo, não FPS exibido no painel.
- A soma disponível registra 61 frames acima de 50 ms, mas não há separação confiável por cena/resolução.
- O coletor capturou `gpu_busy_percentage` de 12%, 32% e 58% somente durante a inicialização. Isso **não** é amostra de gameplay.
- As colunas de fence-wait (`submit`, `readback`, `acquire`) permanecem `unavailable`.

Portanto, não há base para afirmar 30+ FPS, ganho por resolução, ou que a GPU seja o gargalo dominante. O resultado atual é compatível com pressão combinada de CPU/guest, uploads de textura e criação de pipeline, mas isso é hipótese até uma captura controlada.

## Revisão estrutural e achados (formato Symptom / Source / Consequence / Remedy)

### 1. [Critical] “Presented FPS” não representa necessariamente o FPS exibido

- **Symptom:** o contador aceita qualquer `VK_SUCCESS`/`VK_SUBOPTIMAL_KHR` de `vkQueuePresentKHR`, mas o CSV chega a centenas de FPS impossíveis para a tela do S23.
- **Source:** `src/render_metrics.h:67-123` registra a apresentação e usa `elapsed = std::min(1.0, monotonic_seconds - started)` em `:97`, calculando `presentations / elapsed` em `:111-113`. A primeira apresentação tem intervalo zero em `:81`. A amostra chega ao overlay em `src/mcla_app.cpp:133-138` e é rotulada `PRESENT FPS` em `:164-172`.
- **Consequence:** o número mede apresentações aceitas pelo driver em uma janela instável, não a cadência real do painel. Isso invalida comparações de resolução e qualquer promessa de FPS.
- **Remedy:** usar timestamps de apresentação (`VK_GOOGLE_display_timing`, `VK_KHR_present_wait` quando disponíveis, ou FrameTimeline/SurfaceFlinger) e, no mínimo, excluir a primeira amostra e usar uma janela completa de um segundo. Enquanto isso, rotular como “accepted presents/s” e adicionar teste que rejeite inflação acima do refresh esperado.

### 2. [Warning] O Android força 30 FPS depois de aceitar opções que prometem 0/60/120

- **Symptom:** a UI e os extras aceitam diversos limites, mas o runtime sobrescreve todos para 30.
- **Source:** `src/settings_menu.cpp:964-972` aplica `SetFlagByName("mcla_fps", "30")` depois do parse. Em contraste, `android/app/src/main/java/org/mcla/recomp/AppSettings.java:163-171` aceita `-1,0,30,60,120,240`, `DataSetupActivity.java:142-144` oferece 30/60/120/uncapped e `MclaActivity.java:38` encaminha `fps_limit`. `android/README.md:46-54` documenta `fps_limit 0`.
- **Consequence:** a documentação, a tela e o comportamento divergem. Um teste de intent pode parecer aceito, mas não altera o limite nativo.
- **Remedy:** escolher uma política explícita: remover opções não suportadas no Android, ou exibir “30 FPS fixo” e testar que o override é intencionalmente ignorado. Não deixar a interface prometer um valor que o C++ sempre substitui.

### 3. [Warning] Fence-waits estão no cabeçalho do CSV, mas nunca são medidos

- **Symptom:** `fence_submit_wait_ms`, `fence_readback_wait_ms` e `fence_acquire_wait_ms` aparecem sempre como `unavailable`.
- **Source:** `src/mcla_app.cpp:84-103` grava os literais. O patch tem contadores de submit/wait em `patches/rexglue-v0.10.0-mcla.patch:1955-1971` e `:2010-2028`, mas não há uma API que entregue esses deltas ao escritor do CSV.
- **Consequence:** não é possível atribuir o stutter a submit, readback ou acquire, que é justamente a distinção necessária para orientar uma otimização.
- **Remedy:** exportar um snapshot atômico por frame/segundo do command processor para `mcla_app.cpp`, com contagem e microssegundos por origem; cobrir o contrato com teste de monotonicidade e reset por sessão.

### 4. [Warning] Há duas fontes de verdade para as configurações

- **Symptom:** Java valida/persiste settings e o C++ reinterpreta os mesmos nomes, presets e limites.
- **Source:** `AppSettings.java:48-61,84-91,158-200`, `MclaActivity.java:22-49` e `src/settings_menu.cpp:352-381,950-998` mantêm parsers/mapeamentos paralelos.
- **Consequence:** mudanças podem ser aceitas na tela e descartadas no runtime. `src/settings_menu.cpp:983-996` também deixa detalhes salvos impedirem a reaplicação de um preset, salvo origem de linha de comando.
- **Remedy:** definir um schema canônico compartilhado (ou gerar constantes), registrar a origem de cada valor e adicionar teste de integração Java → cvar → efeito observável.

### 5. [Warning] Preset/resolução não têm prova de efeito visual ou de custo

- **Symptom:** relatos de que `super_low` e resolução diferente parecem iguais; não há sweep controlado por cena no conjunto de evidências disponível.
- **Source:** `src/settings_menu.cpp:954-997` converte resolução/preset, enquanto `AppSettings.save` preserva detalhes anteriores em `AppSettings.java:99-136`. Os próprios limites de compatibilidade em `android/README.md:93-95` dizem que as medições ainda exigem validação.
- **Consequence:** é possível estar medindo a mesma configuração em todas as execuções, ou alterar resolução sem alterar o caminho caro do renderer.
- **Remedy:** imprimir no início da sessão a configuração efetiva, executar 20 s por resolução com os mesmos efeitos/cena e comparar apresentações válidas, p50/p95/p99 e uso de GPU/CPU.

### 6. [Warning] O caminho de driver alternativo é heurístico e não validado

- **Symptom:** o app tenta selecionar Turnip/PanVK conforme o renderer e cai para o sistema se o ZIP faltar ou falhar.
- **Source:** `android/app/src/main/java/org/mcla/recomp/GpuDriverManager.java:47-95` escolhe `turnip-adreno740`/`panvk-mali-g52` e extrai bibliotecas; o diretório de assets é ignorado por `android/app/build.gradle:149-153`. O log histórico registrou arquivo Turnip ausente e fallback; a execução fresca usou o Vulkan proprietário do sistema.
- **Consequence:** existe uma decisão de driver que não tem benchmark, validação de licença nem garantia de ABI; o warning de inicialização adiciona ruído e não há prova de ganho.
- **Remedy:** manter o sistema como padrão no S23 até um pacote licenciado, completo e testado existir; registrar renderer/driver efetivo no relatório e comparar A/B antes de forçar qualquer biblioteca.

### 7. [Warning] Warnings de shader/textura e placeholder assíncrono estão sem atribuição de custo

- **Symptom:** a execução registra três `Texture fetch constant ... invalid type` e um `Skipping Vulkan frame presentation due to async placeholder draw usage in this frame`.
- **Source:** mensagens do log do runtime; o caminho de apresentação e métricas está em `src/mcla_app.cpp:133-172`. Não há, nesta captura, tempo por textura, shader, placeholder ou fila.
- **Consequence:** esses eventos podem contribuir para engasgos, mas não há prova de que sejam a causa dominante; ativar flags permissivas cegamente poderia alterar a correção visual.
- **Remedy:** contar ocorrências por shader/asset, medir o tempo de compilação/upload e correlacionar com frames >50 ms antes de mudar a política de tipos inválidos.

### 8. [Suggestion] O CSV não separa sessões, build ou configuração

- **Symptom:** várias execuções aparecem no mesmo `performance-v3.csv`, com `elapsed_s` reiniciando.
- **Source:** `src/mcla_app.cpp:73-105` escreve um cabeçalho único e inicia `process_started` por thread, sem `session_id`, commit, APK, resolução ou preset.
- **Consequence:** análises posteriores podem misturar primeira execução, segunda execução e cenas diferentes.
- **Remedy:** adicionar metadados de sessão (commit, pacote, driver, resolução, preset, vsync, timestamp) e um marcador explícito de início/fim; manter os logs fora do Git.

### 9. [Suggestion] Avisos de agregados devem ser tornados explícitos

- **Symptom:** `cppcheck` acusa sete campos sem inicializador.
- **Source:** `src/settings_menu.cpp:386-397` e `src/touch_controls.cpp:42-54`.
- **Consequence:** hoje não há panic demonstrado, mas uma alteração futura de construção pode transformar intenção implícita em estado indefinido.
- **Remedy:** usar inicializadores padrão nos membros ou uma supressão comentada explicando a inicialização agregada; adicionar teste para o layout padrão de touch.

## O que já foi feito e acertou

- A reserva de memória guest foi corrigida o suficiente para esta build passar de `Runtime::Setup`; o log conserva errno e tamanho.
- O cache Vulkan Android foi integrado no script de patch: `scripts/patch_android_rexglue.py:439-505` carrega e valida vendor/device/UUID; `:507-557` grava via `vkGetPipelineCacheData`, arquivo temporário e rename; `:617-625` passa o handle a `vkCreateGraphicsPipelines`; `:631-683` salva periodicamente e acumula tempo de criação.
- A instrumentação de submit/draw/fence existe no patch em `patches/rexglue-v0.10.0-mcla.patch:1955-1971` e `:1983-2028`.
- O importador usa armazenamento privado (`filesDir/game`), o manifesto declara `FOREGROUND_SERVICE_DATA_SYNC` e `WAKE_LOCK` em `android/app/src/main/AndroidManifest.xml:8-12,38-41`, e a documentação não exige `MANAGE_EXTERNAL_STORAGE`.
- Os 59 testes Python passam; o APK existente instala e inicia no S23; Vulkan do sistema e detecção inicial do gamepad funcionam.
- O `.gitignore` bloqueia APK/XAPK/OBB, chaves, dados de jogo, caches e logs em `.gitignore:1-61,87-100`, reduzindo o risco de vazamento acidental.

## O que falhou ou permanece sem prova

- Não há métrica de apresentação equivalente ao que o painel realmente exibiu; os valores atuais são semanticamente insuficientes.
- Não houve sweep controlado de 1080p/720p/540p, primeira versus segunda execução, por 20 s de cena, com FPS real e p50/p95/p99 comparáveis.
- `gpu_busy_percentage` disponível foi de inicialização, não gameplay; não há trace Perfetto/simpleperf utilizável nesta evidência.
- Fence-waits por origem e compilação de pipelines por segundo ainda não são exportados de modo analisável.
- Um único rastreio de arquivos não prova que todos os `.bik`, áudio ou música sejam dispensáveis; os `.loc` ausentes devem continuar sendo tratados como avisos até uma matriz de cenas.
- O gamepad é enumerado, mas não há prova de que cada ação (direção, aceleração, freio e botões) chega ao jogo.
- O remote atual não é o repositório-alvo autorizado `gabrielbskk/mcla-recomp-android-g`; por isso não houve push nem tentativa de abrir PR.

## Próxima sequência recomendada

1. Corrigir a semântica do contador: timestamps de apresentação ou, temporariamente, janela fixa sem primeira amostra; criar teste contra valores impossíveis.
2. Exportar os contadores do command processor para separar submit/readback/acquire e registrar deltas por segundo.
3. Repetir uma cena determinística em 1080p, 720p e 540p, com `super_low`, 20 s por execução e segunda execução sem reiniciar; coletar `top -H`, GPU busy em gameplay, Perfetto e simpleperf.
4. Só após esses números, medir A/B do cache persistente: frio, quente e invalidação por header.
5. Unificar o schema de settings e tornar explícito o limite Android de 30 FPS, se essa continuar sendo a decisão.
6. Instrumentar a cadeia de gamepad até a ação do jogo e validar a tabela de mapeamento.
7. Manter Vulkan do sistema como baseline e tratar drivers alternativos apenas como experimentos separados, nunca como dependência silenciosa.

## Veredito

O port está **funcional o bastante para abrir e alcançar a seleção de carros no S23 nesta execução, sem crash fatal observado**, e a memória guest/Vulkan/cache persistente apresentam evidência concreta. Ele **não está comprovadamente estável em desempenho nem pronto para declarar 30 FPS ou release**: o contador atual é inválido para FPS de tela, os fence-waits não estão disponíveis e os dados de resolução/cena ainda não são um benchmark controlado.

Nenhuma chave, APK, cache, log bruto, IP pessoal ou dado do jogo foi adicionado a este relatório.
