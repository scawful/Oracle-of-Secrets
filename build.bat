set /P version= Enter Version Number: 
zcompress.exe 1 87200 oos%version%.sfc oos.bin
copy oos%version%.sfc oos%version%x.sfc
asar.exe Oracle_main.asm oos%version%x.sfc
pause