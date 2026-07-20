-- =============================================================================
-- USUARIO DE SOLO LECTURA para el Agente P&A (correr UNA vez como 'sa')
-- Tres candados: db_datareader + DENY de escritura + el agente conecta con
-- ApplicationIntent=ReadOnly. CONTPAQi no se toca.
-- =============================================================================
USE master;
CREATE LOGIN lector_pya WITH PASSWORD = 'CAMBIE-ESTA-CLAVE-Fuerte-2026!',
     CHECK_POLICY = ON;

-- Repita este bloque por CADA base de CONTPAQi (contabilidad ct* y nóminas nom*).
-- Con --descubrir el agente le lista los nombres exactos.
DECLARE @bd sysname, @sql nvarchar(max);
DECLARE bases CURSOR FOR
  SELECT name FROM sys.databases WHERE name LIKE 'ct%' OR name LIKE 'nom%';
OPEN bases; FETCH NEXT FROM bases INTO @bd;
WHILE @@FETCH_STATUS = 0
BEGIN
  SET @sql = N'USE [' + @bd + N'];
    IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = ''lector_pya'')
      CREATE USER lector_pya FOR LOGIN lector_pya;
    ALTER ROLE db_datareader ADD MEMBER lector_pya;
    DENY INSERT, UPDATE, DELETE, ALTER, EXECUTE TO lector_pya;';
  EXEC sp_executesql @sql;
  FETCH NEXT FROM bases INTO @bd;
END
CLOSE bases; DEALLOCATE bases;
PRINT 'lector_pya listo: puede LEER todas las bases CONTPAQi, escribir NINGUNA.';
