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
    'iew\.(branchMispredicts::0)',
    'iew\.exec_(branches::0)',
    'iew\.iewExec(LoadInsts::0)',
    'iew\.exec_(stores::0)',
    'thread(0\.squashedLoads)',
    'thread(0\.squashedStores)',
    '(iqSquashedInstsIssued)',
    '(commitSquashedInsts)',
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
    'switch_cpus\.(branchPredindirectMispredicted)',
    'switch_cpus\.(commit\.branchMispredicts)',
    'switch_cpus\.(iew\.branchMispredict)',
    'switch_cpus\.(iew\.branchMispredicts)',
    'switch_cpus\.(commit\.branchMispredicts)'
]

ipc_target = [
    'switch_cpus\.(ipc)',
]


special_targets = [
    '(cpu\.HPTQoS)',
]
