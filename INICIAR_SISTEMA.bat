@echo off
title Sistema de Auditoria HC - Anexo 5
color 0A
echo ============================================
echo   SISTEMA DE AUDITORIA DE HISTORIAS CLINICAS
echo   Anexo N 5 - Consulta Externa
echo ============================================
echo.
echo [1] Iniciando servidor...
echo.

REM Verificar que credenciales.json existe
if not exist "credenciales.json" (
    echo ERROR: No se encuentra credenciales.json
    echo Copia el archivo credenciales.json a esta carpeta.
    pause
    exit
)

REM Iniciar el servidor Python con miniconda
start "Servidor Auditoria" C:\Users\telesalud\AppData\Local\miniconda3\python.exe app.py

echo [2] Esperando que el servidor inicie...
timeout /t 3 /nobreak > nul

echo [3] Abriendo sistema en el navegador...
start http://192.168.210.36:5000

echo.
echo ============================================
echo  Sistema iniciado correctamente!
echo  URL: http://192.168.210.36:5000
echo  Usuario inicial: admin
echo  Contrasena inicial: admin123
echo ============================================
echo.
echo Presiona cualquier tecla para cerrar esta ventana
echo (El servidor seguira funcionando)
pause > nul
