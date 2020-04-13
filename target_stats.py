standard_targets = [
    '(numCycles)',
    # 'rename\.(.+FullEvents::\d)',
    'cpu\.(committedInsts::\d)',
    'fmt\.(num.*Slots::0)',
    'cpu\.(ipc::\d)',
    'cpu\.(HPTpredIPC)::0',
    '(cpu\.HPTQoS)',
    'fmt\.(mlp_rectification)',
]

slot_targets = [
    'cpu\.(committedInsts::\d)',
    '(fetch\..+)_Slots',
    '(decode\..+)_Slots',
    '(rename\..+)_Slots',
    #'(rename\..+W)aits::0',
    #'(rename\..+F)ullEvents::0',
    '(iew\..+)_Slots',
]

cache_targets = [
    '(dcache.*_m)iss_rate::0',
    '(icache.*_m)iss_rate::0',
    '(l2.*_m)iss_rate::0',
]

branch_targets = [
    'switch_cpus\.(ipc)',
    'switch_cpus\.committed(Insts)',
    #'iew\.(branchMispredicts::0)',
    'iew\.exec_(branches::0)',
    #'iew\.iewExec(LoadInsts::0)',
    #'iew\.exec_(stores::0)',
    '#thread(0\.squashedLoads)',
    #'thread(0\.squashedStores)',
    #'(iqSquashedInstsIssued)',
    #'(commitSquashedInsts)',
    'switch_cpus\.(commit\.branches)',
    'switch_cpus\.branchPred(indirectMis)predicted',
    #'switch_cpus\.(commit\.branchMispredicts)',
    'switch_cpus\.iew\.predicted(TakenIncorrect)',
    'switch_cpus\.iew\.predicted(NotTakenIncorrect)',
    'switch_cpus\.iew\.branch(Misp)redicts',
    #'switch_cpus\.(commit\.branchMispredicts)'
    'switch_cpus\.branchPred\.(lookups)',
    'switch_cpus\.branchPred\.(cond)Predicted',
    'switch_cpus\.branchPred\.(condIncorrect)'
]

util_targets = [
    '(iq_util)ization::0',
    '(rob_util)ization::0',
    'lsq\.(.+_util)ization::0',
]

brief_targets = [
    'switch_cpus\.(ipc)',
    'switch_cpus\.committed(Insts)',
    'switch_cpus\.num(Cycles)',
]

ipc_target = [
    'switch_cpus\.(ipc)',
]


special_targets = [
    '(cpu\.HPTQoS)',
]
