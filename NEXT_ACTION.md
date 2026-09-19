# NEXT ACTION — BOTW GraphicPack only

Do not modify the Cemu binary after the clean raw-trigger bridge passes build/runtime transport validation.

Next work is GraphicPack-only:
1. On GraphicPack/game start, read current equipped bow once and cache its tension.
2. On bow change, update the cached bow/tension.
3. On fire/reload event, increment the event sequence and republish the cached raw trigger command.
4. Keep all bow tables/formulas/BOTW addresses in the GraphicPack.
5. Do not add R2 polling or BOTW state logic to Cemu.
