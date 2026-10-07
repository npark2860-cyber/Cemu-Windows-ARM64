# Resumed tests (2026-09-29)

- User explicitly requested test continuation after the Escape interruption.
- `official-fsr` ended naturally with access violation 0xc0000005 after 18.09 seconds. Windows Application Error 1000 confirms the same official EXE, offset 0x1255b1c. No LSFG code was in that binary. This used changed 960x540 rendering/window settings; it is not evidence that the earlier original settings crash. No FSR-active log appeared before exit. Root cause not yet established.
- Restored the settings from the passing stock runtime (private MLC path adjusted). `Cemu-rebuilt-stock.exe` then displayed the BOTW title menu at roughly 57–60 FPS and exited normally via Alt+F4 after 232.29 seconds, exit code 0. No forced termination.
- This rebuilt check reached the title menu, not gameplay. Further gameplay, LSFG and FSR tests remain pending.
