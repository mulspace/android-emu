set pagination off
set confirm off
set print thread-events off
set disable-randomization off
set auto-load safe-path /nonexistent
set debuginfod enabled off
handle SIGUSR1 nostop noprint pass
handle SIGPIPE nostop noprint pass
handle SIGILL stop print pass
handle SIGSEGV stop print pass
run
echo \n=== STOP REASON ===\n
info program
p $_siginfo
echo \n=== CURRENT THREAD / REGISTERS ===\n
info threads
info registers
echo \n=== HOST INSTRUCTIONS ===\n
x/128bx $pc-64
x/32i $pc-64
x/32bx $pc
x/16i $pc
info symbol $pc
echo \n=== MEMORY MAPPINGS ===\n
info proc mappings
info sharedlibrary
echo \n=== STACKS ===\n
bt 40
thread apply all bt 8
echo \n=== SIGNAL DIAGNOSTIC ONLY: NOT AN APP ACCEPTANCE RESULT ===\n
quit
