# S23 guest-memory initialization investigation — 2026-10-23

## Current result

The V8 app initializes Vulkan on the S23, then fails before loading the game executable. The exported runtime log reports the guest-memory backing-store failure and `Runtime::Setup failed: memory init failed` (`C0000001`). No game assets were opened, so this run says nothing about the import ZIP or game-file compatibility.

The Android process diagnostics record a separate `SIGABRT` during shutdown: Bionic reports `pthread_mutex_lock called on a destroyed mutex`. The native frames include `Presenter::RemoveUIDrawerFromUIThread` and `ReXApp::OnDestroy`. Treat this as a teardown failure after setup has failed; its relationship to the memory error is not yet proven.

## Source findings

- `Memory::Initialize()` requests a shared backing object of `0x120001000` bytes on a 4 KiB-page device. The old message called this a “4gb guest address space” reservation, but the failure occurs before the later guest virtual-address mappings. It was therefore not evidence that a fixed virtual address was occupied.
- The Android POSIX backend has a dynamically loaded `ASharedMemory_create` function pointer. Its `AndroidInitialize()` function was defined but no caller existed in the SDK source. Without initialization, `CreateFileMappingHandle()` takes the `/dev/ashmem` fallback.
- The old backend returned an invalid handle without logging which provider or syscall failed, so the captured app log has no errno. The exact failure from that run cannot be recovered from its log.
- An isolated S23 Termux probe confirmed `ASharedMemory_create(0x120001000)` succeeds, while the unrounded `0x120000000` request returns `EINVAL`. A separate shell-context ashmem `SET_NAME`/`SET_SIZE` probe also succeeded. These probes validate the requested size and available APIs in Termux, but do not prove behavior inside the app process.

## Change prepared in source

The Android SDK patch now calls `AndroidInitialize()` once, immediately before creating the guest-memory backing object. It logs API/function loading, the selected provider, the requested byte count, and the exact errno/string if ASharedMemory or ashmem fails. The generic “4gb reservation” message is replaced with a backing-store-specific message. POSIX map validation now sets `EINVAL` for invalid alignment or an unexpected fixed-address result, so the later mapping diagnostic does not report a stale errno. Each failed guest-view attempt logs its candidate base, view index, requested address/size, file offset, flags/protection, and errno/string. A successful arena log reports the number of views (nine).

The patcher was applied to a clean ReXGlue v0.10.0 worktree and a second run was idempotent. It was also rerun successfully against the existing Termux SDK cache, which contains older Android-specific variants of the chrono and I/O trace patches. Six Python unit checks now cover memory initialization, memory-patch idempotency, rejection of an unknown memory source block, recognition of existing chrono and I/O-trace variants, and guest-map diagnostics/idempotency. They pass. CMake compiled the Android ARM64 objects for `memory_posix.cpp` and `xmemory.cpp` successfully in the existing native build tree. It emitted only unused-parameter and unused `-stdlib=libc++` warnings. One initial compile caught an invalid `.size()` call on the fixed view array; the patch now uses `rex::countof`, and the corrected object compiled. This validates patch generation and C++ object compilation, not the full app link or runtime behavior.

## Required next evidence

1. Build a test package with this patch and run it on the S23 when installation is authorized and ADB is available. At this checkpoint ADB reports no connected device, and no package has been generated or installed in this session.
2. Confirm logs show `Android shared-memory backend initialized` and `Android guest memory backing store created` with the requested size.
3. Confirm all nine guest mappings are created and `Runtime::Setup` proceeds beyond memory initialization. If creation or a mapping still fails, use the new errno log before changing providers or address-space flags.
4. Investigate the destroyed-mutex teardown path separately if it remains after setup passes.
5. Only after Phase 1 passes, capture a comparable FPS baseline and measure each requested rendering/thread change independently. No FPS result is claimed here.

## Privacy

The raw device export remains on the phone/netbook. This report contains only sanitized messages and source-level findings; it excludes raw logs, filesystem paths, identifiers, APKs, game data, and signing material.
