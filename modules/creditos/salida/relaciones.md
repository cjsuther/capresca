# Relaciones inferidas entre tablas — CCyPP

> Claves foráneas **candidatas**, deducidas por nombres de campo compartidos.

> Confirmar cardinalidad e integridad contra los DBC reales.


Total de relaciones candidatas: **202**


### `aliquidar`  ← referenciada por:
- `ccvh`.`no_aporte`  →  `aliquidar`

### `cajacreseg`  ← referenciada por:
- `cajaliq`.`no_subagencia`  →  `cajacreseg`
- `cj_crsghis`.`dni`  →  `cajacreseg`
- `cj_crsghis`.`id_ingreso`  →  `cajacreseg`
- `cj_liqhis`.`no_subagencia`  →  `cajacreseg`
- `liquidaciones`.`no_subagencia`  →  `cajacreseg`
- `maeagencias`.`no_subagencia`  →  `cajacreseg`

### `cajaliq`  ← referenciada por:
- `cajacreseg`.`no_liquida`  →  `cajaliq`
- `ccvh`.`no_liquida`  →  `cajaliq`
- `cj_crsghis`.`no_liquida`  →  `cajaliq`
- `cj_liqhis`.`no_sorteo`  →  `cajaliq`
- `egresos`.`no_liquida`  →  `cajaliq`
- `jjimpjue`.`no_sorteo`  →  `cajaliq`
- `liquidaciones`.`no_sorteo`  →  `cajaliq`
- `maejugadas`.`no_sorteo`  →  `cajaliq`
- `maeprestamos`.`no_liquida`  →  `cajaliq`
- `osolicitud`.`no_liquida`  →  `cajaliq`
- `sol`.`no_liquida`  →  `cajaliq`
- `solicitud`.`no_liquida`  →  `cajaliq`
- `solid`.`no_liquida`  →  `cajaliq`
- `solprn`.`no_liquida`  →  `cajaliq`

### `cajapagos`  ← referenciada por:
- `cajaforpag`.`no_recibo`  →  `cajapagos`
- `cajaliq`.`no_recibo`  →  `cajapagos`
- `cj_liqhis`.`no_recibo`  →  `cajapagos`
- `egresos`.`no_recibo`  →  `cajapagos`
- `hisolicitud`.`no_recibo`  →  `cajapagos`
- `jjimpjue`.`no_recibo`  →  `cajapagos`
- `maeprestamos`.`no_recibo`  →  `cajapagos`
- `osolicitud`.`no_recibo`  →  `cajapagos`
- `sol`.`no_recibo`  →  `cajapagos`
- `solicitud`.`no_recibo`  →  `cajapagos`
- `solid`.`no_recibo`  →  `cajapagos`

### `crcliact`  ← referenciada por:
- `cajacreseg`.`no_credito`  →  `crcliact`
- `ccvh`.`no_credito`  →  `crcliact`
- `cj_crsghis`.`no_credito`  →  `crcliact`
- `egresos`.`no_credito`  →  `crcliact`
- `himaecuotas`.`no_credito`  →  `crcliact`
- `hmc`.`no_credito`  →  `crcliact`
- `maecuotas`.`no_credito`  →  `crcliact`
- `maeid`.`no_credito`  →  `crcliact`
- `maeprestamos`.`no_credito`  →  `crcliact`
- `v_cierrecred`.`no_credito`  →  `crcliact`

### `ctrlage`  ← referenciada por:
- `maeagencias`.`cod_age`  →  `ctrlage`

### `egresos`  ← referenciada por:
- `ccvh`.`no_op`  →  `egresos`
- `envios`.`no_cuota`  →  `egresos`
- `himaecuotas`.`no_cuota`  →  `egresos`
- `hisolicitud`.`no_cheque`  →  `egresos`
- `hisolicitud`.`no_op`  →  `egresos`
- `hmc`.`no_cuota`  →  `egresos`
- `jub_ctas`.`no_cheque`  →  `egresos`
- `jub_ctas`.`no_cuota`  →  `egresos`
- `jub_ctas`.`no_op`  →  `egresos`
- `liquid_dat`.`id_ano`  →  `egresos`
- `liquid_dat`.`id_letra`  →  `egresos`
- `liquid_dat`.`id_nro`  →  `egresos`
- `maecuotas`.`no_cuota`  →  `egresos`
- `maeid`.`no_cuota`  →  `egresos`
- `maeprestamos`.`no_cheque`  →  `egresos`
- `maeprestamos`.`no_op`  →  `egresos`
- `osolicitud`.`no_cheque`  →  `egresos`
- `osolicitud`.`no_op`  →  `egresos`
- `parte1`.`id_ano`  →  `egresos`
- `parte1`.`id_letra`  →  `egresos`
- `parte1`.`id_nro`  →  `egresos`
- `parte1`.`id_tramite`  →  `egresos`
- `parte2`.`id_tramite`  →  `egresos`
- `parte3`.`id_letra`  →  `egresos`
- `parte3`.`id_nro`  →  `egresos`
- `parte3`.`id_tramite`  →  `egresos`
- `parte4`.`id_letra`  →  `egresos`
- `parte4`.`id_nro`  →  `egresos`
- `parte4`.`id_tramite`  →  `egresos`
- `pases`.`id_ano`  →  `egresos`
- `pases`.`id_letra`  →  `egresos`
- `pases`.`id_nro`  →  `egresos`
- `pases`.`id_tramite`  →  `egresos`
- `resol`.`id_ano`  →  `egresos`
- `resol`.`id_letra`  →  `egresos`
- `resol`.`id_nro`  →  `egresos`
- `resol`.`id_tramite`  →  `egresos`
- `resoluciones`.`id_ano`  →  `egresos`
- `resoluciones`.`id_letra`  →  `egresos`
- `resoluciones`.`id_nro`  →  `egresos`
- `resoluciones`.`id_tramite`  →  `egresos`
- `sol`.`no_op`  →  `egresos`
- `solicitud`.`no_cheque`  →  `egresos`
- `solicitud`.`no_op`  →  `egresos`
- `solid`.`no_cheque`  →  `egresos`
- `solid`.`no_op`  →  `egresos`
- `solprn`.`no_op`  →  `egresos`
- `tramites`.`id_ano`  →  `egresos`
- `tramites`.`id_letra`  →  `egresos`
- `tramites`.`id_nro`  →  `egresos`
- `tramites`.`id_tramite`  →  `egresos`
- `v_liq_datos`.`id_ano`  →  `egresos`
- `v_liq_datos`.`id_letra`  →  `egresos`
- `v_liq_datos`.`id_nro`  →  `egresos`

### `envios`  ← referenciada por:
- `maedio`.`no_agente`  →  `envios`
- `maestrodio`.`no_agente`  →  `envios`
- `seguros`.`no_agente`  →  `envios`
- `titulares`.`no_agente`  →  `envios`

### `hisolicitud`  ← referenciada por:
- `osolicitud`.`no_banco`  →  `hisolicitud`
- `osolicitud`.`no_credpp`  →  `hisolicitud`
- `sol_activas`.`no_credpp`  →  `hisolicitud`
- `solicitud`.`no_banco`  →  `hisolicitud`
- `solicitud`.`no_credpp`  →  `hisolicitud`
- `solid`.`no_credpp`  →  `hisolicitud`
- `solprn`.`no_credpp`  →  `hisolicitud`

### `hmc`  ← referenciada por:
- `maecuotas`.`no_envio`  →  `hmc`

### `jub_ctas`  ← referenciada por:
- `sol_jubi`.`no_resolucion`  →  `jub_ctas`

### `lin`  ← referenciada por:
- `lineacred`.`no_linea`  →  `lin`
- `linid`.`no_linea`  →  `lin`
- `local_linea`.`no_linea`  →  `lin`
- `lolineanueva`.`no_linea`  →  `lin`
- `olinea`.`no_linea`  →  `lin`

### `lineacred`  ← referenciada por:
- `aliquidar`.`linea`  →  `lineacred`
- `cpg`.`linea`  →  `lineacred`
- `cps`.`linea`  →  `lineacred`
- `envios`.`linea`  →  `lineacred`
- `hisolicitud`.`linea`  →  `lineacred`
- `maeprestamos`.`linea`  →  `lineacred`
- `osolicitud`.`linea`  →  `lineacred`
- `sol`.`linea`  →  `lineacred`
- `sol_activas`.`linea`  →  `lineacred`
- `solicitud`.`linea`  →  `lineacred`
- `solid`.`linea`  →  `lineacred`
- `solprn`.`linea`  →  `lineacred`

### `maeagencias`  ← referenciada por:
- `cajacreseg`.`no_agencia`  →  `maeagencias`
- `cajaliq`.`cod_agencia`  →  `maeagencias`
- `cajaliq`.`no_agencia`  →  `maeagencias`
- `cajapagos`.`cod_agencia`  →  `maeagencias`
- `cj_crsghis`.`no_agencia`  →  `maeagencias`
- `cj_liqhis`.`no_agencia`  →  `maeagencias`
- `ctrlage`.`no_agencia`  →  `maeagencias`
- `jjimpjue`.`no_agencia`  →  `maeagencias`
- `liquidaciones`.`cod_agencia`  →  `maeagencias`
- `liquidaciones`.`no_agencia`  →  `maeagencias`
- `t_liq`.`cod_agencia`  →  `maeagencias`
- `titulares`.`no_doc`  →  `maeagencias`
- `ttmp`.`no_iva`  →  `maeagencias`

### `maeclientes`  ← referenciada por:
- `aliquidar`.`cuil`  →  `maeclientes`
- `cajacreseg`.`cuil`  →  `maeclientes`
- `cj_crsghis`.`cuil`  →  `maeclientes`
- `crcliact`.`cuil`  →  `maeclientes`
- `ctrlenv`.`cuil`  →  `maeclientes`
- `egresos`.`cuil`  →  `maeclientes`
- `jub_ctas`.`cuil`  →  `maeclientes`
- `liqsegur`.`cuil`  →  `maeclientes`
- `maedio`.`ccuil`  →  `maeclientes`
- `maedio`.`cidcliente`  →  `maeclientes`
- `maedio`.`cuil`  →  `maeclientes`
- `maestrodio`.`ccuil`  →  `maeclientes`
- `maestrodio`.`cidcliente`  →  `maeclientes`
- `nro`.`cuil`  →  `maeclientes`
- `oec`.`cuil`  →  `maeclientes`
- `osolicitud`.`ga_idcli`  →  `maeclientes`
- `personas`.`ccuil`  →  `maeclientes`
- `recibidos`.`ccuil`  →  `maeclientes`
- `recleg`.`cuil`  →  `maeclientes`
- `seguros`.`cuil`  →  `maeclientes`
- `sol_jubi`.`cuil`  →  `maeclientes`
- `solicitud`.`ga_idcli`  →  `maeclientes`
- `solprn`.`ga_idcli`  →  `maeclientes`
- `titulares`.`cuil`  →  `maeclientes`

### `maedio`  ← referenciada por:
- `maestrodio`.`ndoc`  →  `maedio`

### `maejuegos`  ← referenciada por:
- `cajaliq`.`cod_juego`  →  `maejuegos`
- `cj_liqhis`.`cod_juego`  →  `maejuegos`
- `jjimpjue`.`cod_juego`  →  `maejuegos`
- `liquidaciones`.`cod_juego`  →  `maejuegos`
- `maejugadas`.`cod_juego`  →  `maejuegos`

### `organismos`  ← referenciada por:
- `crcliact`.`corga`  →  `organismos`
- `crcliact`.`norgano`  →  `organismos`
- `maeclientes`.`corga`  →  `organismos`
- `maeclientes`.`norgano`  →  `organismos`
- `maestrodio`.`norgano`  →  `organismos`
- `personas`.`norgano`  →  `organismos`
- `recibidos`.`corga`  →  `organismos`
- `recibidos`.`norgano`  →  `organismos`
- `recleg`.`norgano`  →  `organismos`
- `saf`.`norgano`  →  `organismos`

### `osolicitud`  ← referenciada por:
- `sol`.`cod_inst`  →  `osolicitud`

### `resol`  ← referenciada por:
- `resoluciones`.`cod_mot`  →  `resol`

### `resoluciones`  ← referenciada por:
- `hisolicitud`.`no_resol`  →  `resoluciones`
- `maeprestamos`.`no_resol`  →  `resoluciones`
- `osolicitud`.`no_resol`  →  `resoluciones`
- `sol`.`no_resol`  →  `resoluciones`
- `sol_activas`.`no_resol`  →  `resoluciones`
- `solicitud`.`no_resol`  →  `resoluciones`
- `solid`.`no_resol`  →  `resoluciones`
- `solprn`.`no_resol`  →  `resoluciones`

### `solicitud`  ← referenciada por:
- `crorig`.`no_solicitud`  →  `solicitud`
- `egresos`.`no_solicitud`  →  `solicitud`
- `hisolicitud`.`no_solicitud`  →  `solicitud`
- `jub_ctas`.`no_solicitud`  →  `solicitud`
- `maeprestamos`.`no_solicitud`  →  `solicitud`
- `osolicitud`.`no_solicitud`  →  `solicitud`
- `sol`.`no_solicitud`  →  `solicitud`
- `sol_activas`.`no_solicitud`  →  `solicitud`
- `sol_jubi`.`no_solicitud`  →  `solicitud`
- `solgas`.`no_solicitud`  →  `solicitud`
- `solid`.`no_solicitud`  →  `solicitud`
- `solprn`.`no_solicitud`  →  `solicitud`
