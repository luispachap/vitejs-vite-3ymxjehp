# Agente P&A ↔ CONTPAQ — instalación (una sola vez, ~15 min)

**Qué hace:** todas las mañanas lee CONTPAQi (solo lectura, garantizado) y
alimenta el sistema: resultados del cliente, carga social proyectada y la
predicción de impuestos a mitad de mes. Nadie captura nada.

1. **En Render** (Environment): agregue `AGENTE_CONTPAQ_TOKEN` con una clave
   larga inventada (30+ caracteres). Guárdela: es la misma del paso 4.
2. **En la PC del despacho** (la de CONTPAQi): instale Python de python.org
   (palomee "Add to PATH") y en una ventana de comandos:
   `py -m pip install pyodbc requests`
3. **Usuario de solo lectura:** abra SQL Server Management Studio como `sa` y
   ejecute `crear_usuario_lectura.sql` (cambie la clave del primer renglón).
4. **Configure:** copie `config.ini.ejemplo` → `config.ini` y llénelo. Para
   ver los nombres exactos de las bases: `py agente_contpaq.py --descubrir`
   (si algún campo difiere, ajústelo en CAMPOS, al inicio del script).
5. **Pruebe sin enviar:** `py agente_contpaq.py --prueba`
6. **Envíe:** `py agente_contpaq.py --enviar` — y prográmelo diario:
   `schtasks /Create /SC DAILY /ST 07:00 /TN "Agente P&A CONTPAQ" /TR "py C:\pya\agente_contpaq.py --enviar"`

**Seguridad:** el SQL Server jamás se expone a internet: el agente lee LOCAL
y empuja resúmenes cifrados (HTTPS) con su token. Tres candados de lectura:
usuario db_datareader + DENY de escritura + conexión ReadOnly.
