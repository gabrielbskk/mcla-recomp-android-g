# AGENTS.md — MCLA Recomp Android

Regras permanentes para qualquer agente (Codex ou outro) neste repositório. Estas regras valem mais que qualquer objetivo ou plano antigo.

## Projeto

- Port nativo do Midnight Club: Los Angeles (Xbox 360) para Android ARM64.
- Stack: ReXGlue v0.10.0 (recompilação estática), SDL3, Vulkan (backend Xenos).
- Alvo: Galaxy S23 (SM-S911B, Snapdragon 8 Gen 2, Adreno 740), Android 16.
- Pacote: org.mcla.recomp. Os dados do jogo ficam no armazenamento privado do app (filesDir/game), importados de um ZIP ou pasta escolhidos pelo usuário.

## Segurança e repositório

- Push só para https://github.com/gabrielbskk/mcla-recomp-android-g (privado). Confirme que é privado antes do primeiro push. Nunca envie nada a outro repositório.
- Trabalhe em branch própria, com commits pequenos e mensagens claras. Nunca use force push.
- Nunca commite: chaves de assinatura, keystores, tokens, .env, XAPK, OBB, APKs, dados do jogo (xex, rpf, bik, nxeart), caches de pipeline/shader nem logs com dados pessoais.
- Antes de cada push, confira o .gitignore e liste os arquivos que serão enviados.
- Não copie código de repositórios de referência. Leia e aprenda a abordagem.

## Build

- O Gradle completo NÃO roda no Termux (CMake e AAPT2 do SDK são x86_64). Não tente de novo.
- Use o processo manual ARM64: compile libmain.so, librexruntime.so e librexgpu-xenos.so com o Clang/CMake ARM64 do Termux, troque-as num APK base, alinhe e assine.
- Não altere o ReXGlue em cache sem registrar o patch em scripts/ e cobri-lo com teste em tests/.

## Assinatura e instalação

- Use sempre a mesma chave. Nunca troque a assinatura sem me avisar.
- O app instalado usa o certificado Android Debug. Antes de assinar, compare o SHA-256 do certificado com o do app instalado (apksigner verify --print-certs).
- Nunca desinstale o app nem apague dados privados ou saves sem minha confirmação explícita. Desinstalar apaga os dados importados (cerca de 6,5 GB).

## ADB

- Antes de qualquer instalação ou teste no S23, peça para eu conectar o ADB e espere minha confirmação.
- Nunca pule um teste no aparelho nem declare resultado de aparelho sem a saída do ADB.

## Método de trabalho

- Meça antes de declarar. Nunca declare causa sem o log (errno, trecho de log, arquivo e linha) nem ganho de FPS sem medição antes e depois.
- Se um item não puder ser provado, pare e relate o motivo em vez de declarar sucesso.
- Se a mesma abordagem falhar 3 vezes, pare e relate o log, o que foi tentado e o próximo passo sugerido.
- Cite arquivo e linha em cada afirmação sobre código. Se não achar, diga "não achei".
- Relatórios curtos: o que foi feito, o que foi provado, o que não foi, riscos.

## Ordem das etapas atuais

1. Memória: a v8 falha em Runtime::Setup ("Unable to reserve the 4gb guest address space", C0000001). A reserva pede um arquivo de apoio de 0x120000000 bytes via ASharedMemory_create (memory_posix.cpp). Registrar errno, implementar fallback com memfd_create + ftruncate64 e provar que o runtime passa de Runtime::Setup.
2. Arquivos: log de arquivos abertos até a seleção de carros; dizer se o jogo tenta abrir .bik, nxeart ou root_directory_padding.pad.
3. Medição: top -H, gpu_busy_percentage, perfetto, simpleperf e origem de cada fence-wait (submit, readback, acquire).
4. VkPipelineCache persistente em filesDir (hoje VK_NULL_HANDLE em pipeline_cache.cpp), com medição de engasgos antes e depois.

Só avance para a etapa seguinte quando a anterior estiver provada.

## Arquivos obrigatórios do jogo (validação de importação)

default.xex, xarchive_cache.rpf, xarchive_audio.rpf, xarchive_audlo.rpf, xarchive_music.rpf. Os .bik são opcionais até haver prova de runtime.
