[BotW_AdaptiveTrigger_V208]
moduleMatches = 0x6267BFD0

.origin = codecave

AdaptiveTriggerState:
.uint 0

BowTensionTable:
.uint 0,41,50,48,40,0,50,0,0,46,0,61,0,51,51,50,45,56,0,0,0,0,0,79,0,0,56,60,63,46,71,0,67,85,0,62,73,0,40,0,50,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,85,65

UpdateAdaptiveTriggerState:
li r3, 0
lis r4, 0x1047
lwz r4, -0x6688(r4)
cmpwi r4, 0
beq StoreAdaptiveTriggerState
addis r4, r4, 0x4
lwz r4, -0x7ed0(r4)
cmpwi r4, 0
beq StoreAdaptiveTriggerState
lwz r5, 0x18(r4)
cmpwi r5, 0
beq StoreAdaptiveTriggerState

lwz r6, 0x00(r5)
lis r7, 0x5765
ori r7, r7, 0x6170
cmpw r6, r7
bne StoreAdaptiveTriggerState
lwz r6, 0x04(r5)
lis r7, 0x6f6e
ori r7, r7, 0x5f42
cmpw r6, r7
bne StoreAdaptiveTriggerState
lwz r6, 0x08(r5)
lis r7, 0x6f77
ori r7, r7, 0x5f30
cmpw r6, r7
bne StoreAdaptiveTriggerState

lbz r6, 0x0c(r5)
addi r6, r6, -48
cmplwi r6, 9
bgt StoreAdaptiveTriggerState
lbz r7, 0x0d(r5)
addi r7, r7, -48
cmplwi r7, 9
bgt StoreAdaptiveTriggerState
mulli r6, r6, 10
add r6, r6, r7
cmplwi r6, 72
bgt StoreAdaptiveTriggerState
slwi r6, r6, 2
lis r7, BowTensionTable@ha
addi r7, r7, BowTensionTable@l
lwzx r3, r7, r6

StoreAdaptiveTriggerState:
lis r4, AdaptiveTriggerState@ha
stw r3, AdaptiveTriggerState@l(r4)
blr

.callback frame UpdateAdaptiveTriggerState
.adaptiveTrigger right bow AdaptiveTriggerState 2
