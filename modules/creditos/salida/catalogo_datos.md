# Catálogo de datos preliminar — CCyPP (inferido del código)

> Generado por ingeniería inversa. Archivos analizados: 174 `.prg` + 2512 binarios (scx/frx/vcx).

> Tablas candidatas: **157** · Alias con campos sin tabla resuelta: **624**.

> ⚠️ Tipos de campo inferidos por convención VFP (prefijo). Confirmar contra los DBC reales cuando haya backup.


## Base: `agjscaja`

### `cajacreseg`  ·  280 refs  ·  48 archivos
- Campos observados (46): `fecha_pago`, `lrevertida`, `fecha_alta`, `no_credito`, `cualcuo`, `total_gral`, `total`, `moncuo`, `interes`, `ivain`, `cajero`, `consor`, `cuil`, `dni`, `fecha_carga`, `intereses`, `iva`, `cupon`, `fecha`, `codcon`, `id_ingreso`, `fecrev`, `moneda`, `coding`, `cmotivorev`, `no_liquida`, `banco`, `mes`, `ctactble`, `cheque`, `tasa`, `no_agencia`, `gastos`, `no_subagencia`, `nintnornodev`, `nivaintnodev`, `nsegnodev`, `nivasegnodev`, `ngastosnodev`, `nivagasnodev`

### `cajaliq`  ·  122 refs  ·  49 archivos
- Campos observados (31): `cod_agencia`, `no_agencia`, `cod_juego`, `no_subagencia`, `fecha_vto`, `fecha_pago`, `total_gral`, `no_recibo`, `moneda`, `intereses`, `iva`, `total`, `lanula`, `no_sorteo`, `cajero`, `cjuego`, `modalidad`, `fecha_sorteo`, `interior`, `com_agencia`, `fdo_gtia`, `ing_brutos`, `municap`, `ncreditosv`, `ndebitosv`, `com_premios`, `t_com_subage`, `calta`, `lscim`, `multas`, `com_subage`

### `cajaforpag`  ·  47 refs  ·  17 archivos
- Campos observados (6): `moneda`, `fecha_pago`, `cheque`, `cajero`, `no_recibo`, `importe`

### `cajapagos`  ·  47 refs  ·  18 archivos
- Campos observados (9): `bonos`, `cobrado_total`, `cobrado_bonos`, `cobrado_pesos`, `fecha_pago`, `cajero`, `no_recibo`, `cod_agencia`, `total`

### `cajaliqx`  ·  18 refs  ·  8 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `cj_crsghis`  ·  16 refs  ·  8 archivos
- Campos observados (35): `lrevertida`, `total`, `total_gral`, `fecha_pago`, `id_ingreso`, `intereses`, `iva`, `dni`, `moncuo`, `interes`, `ivain`, `fecha`, `coding`, `fecha_carga`, `fecha_carg`, `cualcuo`, `moneda`, `no_liquida`, `cuil`, `norden`, `no_agencia`, `cajero`, `fecha_alta`, `fecha_modi`, `no_credito`, `fecrev`, `ctactble`, `nintnornodev`, `nivaintnodev`, `nsegnodev`, `nivasegnodev`, `ngastosnodev`, `nivagasnodev`, `cheque`, `banco`

### `cj_liqhis`  ·  12 refs  ·  6 archivos
- Campos observados (23): `total_gral`, `lanula`, `cod_juego`, `modalidad`, `cjuego`, `no_sorteo`, `fecha_sorteo`, `no_agencia`, `no_subagencia`, `moneda`, `com_agencia`, `fdo_gtia`, `ing_brutos`, `municap`, `ncreditosv`, `ndebitosv`, `t_com_subage`, `total`, `fecha_vto`, `intereses`, `iva`, `fecha_pago`, `no_recibo`

### `cajaliqq`  ·  12 refs  ·  6 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `cierrejuegos`  ·  12 refs  ·  3 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `cierremoneda`  ·  12 refs  ·  3 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `cajacresegx`  ·  5 refs  ·  5 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `cj_paghis`  ·  5 refs  ·  3 archivos
- Campos observados (4): `cobrado_total`, `cobrado_bonos`, `cobrado_pesos`, `bonos`

### `v_cierrecred`  ·  4 refs  ·  2 archivos
- Campos observados (1): `no_credito`

### `cj_liqhisq`  ·  4 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `cj_fpaghis`  ·  3 refs  ·  3 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `v_cjctacte`  ·  1 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)


## Base: `agjscreditos`

### `solicitud`  ·  512 refs  ·  162 archivos
- Campos observados (158): `linea`, `no_solicitud`, `estado`, `fecha_soli`, `montosol`, `no_credpp`, `isellado`, `iquebranto`, `no_resol`, `fecha_resol`, `fecha_pago`, `nivaqeb`, `importepp`, `no_op`, `nivaori`, `ga_cuil`, `nivaadm`, `nigori`, `igastos`, `cubica`, `fecha_op`, `ga_apenom`, `ga_organo`, `nivasel`, `lote`, `ga_agente`, `tasa`, `debauto`, `diferencia`, `g2_cuil`, `g3_cuil`, `fecha_liquida`, `tna`, `gasista_nomb`, `cant_cuotas`, `no_liquida`, `ga_orga`, `no_recibo`, `ga_idcli`, `g2_apenom`

### `lineacred`  ·  408 refs  ·  129 archivos
- Campos observados (44): `denominacion`, `no_linea`, `cartera`, `ctactble`, `tasa`, `lhabilitada`, `gas_adm`, `nmoradia`, `tna`, `gracia`, `capital_max`, `gas_qeb`, `ncan_apor`, `npor_apor1`, `npor_apor2`, `npor_apor3`, `npor_apor4`, `npor_apor5`, `lgoripor`, `nvalggaa`, `lscig`, `gas_sel`, `ngori`, `nvalqueb`, `nmora`, `cuotas_cap`, `lpagintgra`, `livasint`, `tipo_calculo`, `livaadm`, `moneda`, `ncant_pagos`, `lbonifica`, `nhasta0`, `nbonif0`, `nhasta1`, `nbonif1`, `nbonif2`, `cupo`, `livaqeb`

### `maecuotas`  ·  333 refs  ·  96 archivos
- Campos observados (39): `fecha_vto`, `no_cuota`, `no_credito`, `estado`, `capital`, `iva_interes`, `interes`, `total_vdo`, `interes_puni`, `iva_puni`, `interes_resar`, `iva_resar`, `total`, `ngadm`, `fecha_pago`, `nivaadm`, `total_pagado`, `ngseg`, `nivaseg`, `cobra`, `int_no_dev`, `fecha_envio`, `nrecibo`, `ivai_no_dev`, `gaadm_no_d`, `iva_ad_no_d`, `fecha_modi`, `nitna`, `nipuni`, `lbaja`, `niresa`, `cmotbaja`, `no_envio`, `cvarios1`, `fecha_alta`, `fecbaja`, `cvarios2`, `fec_res_ind`, `nro_res_ind`

### `maeclientes`  ·  107 refs  ·  23 archivos
- Campos observados (38): `capenom`, `norgano`, `eagente`, `cidcliente`, `ccuil`, `nsueldo`, `csexo`, `lcapre`, `fnacim`, `cdomicilio`, `clocalidad`, `corga`, `cbarrio`, `cdepto`, `ccpa`, `ctelefono`, `ccbucta`, `ldebauto`, `ntipocli`, `edni`, `esucursal`, `ecuenta`, `cemail`, `ffperm`, `egarantias`, `nmontogar`, `ncancre`, `ncuotacre`, `ncatfun`, `fecbaja`, `lbaja`, `cmotbaja`, `cbenef`, `falta`, `fmodi`, `ccatfun`, `calta`, `cmodi`

### `crcliact`  ·  102 refs  ·  36 archivos
- Campos observados (48): `nlinea`, `cuil`, `nocred`, `caracter`, `nctacan`, `norgano`, `corga`, `npzotot`, `lagjs`, `lgarcapre`, `nagente`, `ncartera`, `nhaberes`, `lgargar`, `lpaga_con_pp`, `nimpcta`, `cestado`, `fecha`, `cidcli`, `dbf`, `nimpcan`, `nctamor`, `nimpmor`, `ncancta`, `nsdonor`, `csexo`, `lmora`, `ldebauto`, `nctaact`, `nimpact`, `nctabaj`, `nimpbaj`, `nctaenv`, `nimpenv`, `nctafal`, `nimpfal`, `nctajud`, `nimpjud`, `nctaleg`, `nimpleg`

### `turnos`  ·  47 refs  ·  15 archivos
- Campos observados (18): `fecha`, `ctipo`, `nturno`, `lusado`, `capenoms`, `nlinea`, `cmodi`, `cuilsol`, `nsueldos`, `nmargens`, `norganos`, `nagentes`, `lvigente`, `lautoriza`, `calta`, `falta`, `descripcion`, `fmodi`

### `solicitudx`  ·  39 refs  ·  11 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `sol_jubi`  ·  26 refs  ·  9 archivos
- Campos observados (17): `no_solicitud`, `cuil`, `expediente`, `no_beneficio`, `no_resolucion`, `baja_mes`, `fecha_resolucion`, `liquidada`, `fecha_alta`, `depto`, `cancelada`, `domicilio`, `localidad`, `telefono`, `fecha_modi`, `nroprorroga`, `monto`

### `hisolicitud`  ·  24 refs  ·  15 archivos
- Campos observados (29): `linea`, `montosol`, `igastos`, `isellado`, `iquebranto`, `estado`, `no_resol`, `fecha_resol`, `no_op`, `fecha_op`, `fecha_pago`, `cant_cuotas`, `tna`, `tasa`, `no_solicitud`, `fecha_soli`, `ngseg`, `ngadm`, `nigori`, `nivaori`, `nivaqeb`, `nivaadm`, `importepp`, `no_credpp`, `fecha_liquida`, `lanulada`, `no_recibo`, `no_banco`, `no_cheque`

### `envios`  ·  22 refs  ·  10 archivos
- Campos observados (24): `no_cuota`, `linea`, `total_vdo`, `no_cuil`, `no_agente`, `fecha_vto`, `descontada`, `cobra`, `cancelada`, `fecha_envi`, `codigo`, `cperiodo`, `no_soli`, `capital`, `interes`, `iva_inte`, `total`, `int_puni`, `iva_puni`, `int_resar`, `iva_resar`, `total_pagado`, `ncuota`, `no_cred`

### `maecuotasx`  ·  22 refs  ·  8 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `jub_ctas`  ·  17 refs  ·  8 archivos
- Campos observados (12): `no_solicitud`, `no_cuota`, `no_resolucion`, `fecha_vto`, `fecha_pago`, `fecha_resolucion`, `no_op`, `fecha_op`, `cuil`, `fecha_alta`, `codban`, `no_cheque`

### `himaecuotas`  ·  13 refs  ·  12 archivos
- Campos observados (20): `fecha_vto`, `no_cuota`, `fecha_pago`, `no_credito`, `estado`, `nitna`, `capital`, `interes`, `iva_interes`, `total`, `interes_puni`, `iva_puni`, `interes_resar`, `iva_resar`, `total_vdo`, `total_pagado`, `ngadm`, `ngseg`, `nivaadm`, `lbaja`

### `v_devengaasi1`  ·  4 refs  ·  2 archivos
- Campos observados (1): `cartera`

### `v_ctaspendalls`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `v_ctaspendallg`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `maecuotasq`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `solicitudq`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `lineacredq`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `paramcred`  ·  2 refs  ·  2 archivos
- Campos observados (3): `tabla`, `denominacion`, `no_parametro`

### `v_maeclientes_tb`  ·  1 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `v_infodeuda`  ·  1 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `pgsql_maecuotas`  ·  1 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `maeprestamos`  ·  1 refs  ·  1 archivos
- Campos observados (24): `no_credito`, `cantidad_cuotas`, `fecha_pago`, `monto_otorgado`, `no_liquida`, `fecha_resol`, `no_resol`, `capcta`, `intcta`, `fecha_liquida`, `no_op`, `no_recibo`, `impprepag`, `fecha_op`, `no_cheque`, `gastos_adm`, `gastos_sellado`, `gastos_quebranto`, `no_solicitud`, `linea`, `gracia`, `tasa`, `nocredpp`, `int1cta`


## Base: `agjsdespacho`

### `resoluciones`  ·  133 refs  ·  19 archivos
- Campos observados (21): `importe`, `fec_res`, `nro_res`, `fec_real`, `tipo_res`, `id_letra`, `id_nro`, `id_ano`, `id_tramite`, `nro_real`, `modelo`, `texto`, `i_d`, `cod_mot`, `modi_usuario`, `modi_fecha`, `nro_op`, `fec_op`, `disposicion`, `lanulada`, `fanula`


## Base: `agjsegresos`

### `egresos`  ·  301 refs  ·  86 archivos
- Campos observados (39): `no_credito`, `no_liquida`, `fecha_liquida`, `cuil`, `total`, `fecha_op`, `no_op`, `fec_res`, `nro_res`, `importe`, `fechapago`, `no_recibo`, `detalle`, `lanulada`, `no_cheque`, `banco`, `tipo_egreso`, `id_letra`, `id_nro`, `id_ano`, `no_cuota`, `id_tramite`, `ccbu`, `fecha_modi`, `tipo_res`, `no_solicitud`, `ltransf`, `cmotanu`, `fecanu`, `fecha_alta`, `cnrofac`, `lenvtransf`, `fecha_ant`, `disposicion`, `fecha_dispo`, `cnrorec`, `ccuiltrans`, `ffectranf`, `cusutransf`

### `egresosx`  ·  22 refs  ·  15 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `paramegre`  ·  2 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)


## Base: `agjsgeneral`

### `paramgral`  ·  154 refs  ·  33 archivos
- Campos observados (19): `cdescripcion`, `etabla`, `ecodigo`, `lvalor`, `cvalor`, `cdesred`, `evalor1`, `evalor3`, `fvalor`, `evalor2`, `nvalor2`, `nvalor3`, `nvalor1`, `cdenominacion`, `codigop`, `cvalor1`, `cvalor2`, `fvalor1`, `fvalor2`

### `organismos`  ·  119 refs  ·  41 archivos
- Campos observados (7): `nombre`, `capresca`, `debauto`, `nagrupa`, `nagrupa1`, `nombreagrupa1`, `domicilio`

### `auditoria`  ·  31 refs  ·  9 archivos
- Campos observados (1): `maquina`

### `maedio`  ·  24 refs  ·  10 archivos
- Campos observados (18): `no_agente`, `fnacim`, `cuil`, `tdoc`, `ndoc`, `ccuil`, `domicilio`, `clasecargo`, `fingre`, `estciv`, `fecha_actual`, `localidad`, `departamen`, `categ`, `nacion`, `fperm`, `cidcliente`, `ctabco`

### `saf`  ·  20 refs  ·  8 archivos
- Campos observados (5): `descripcio`, `nsaf`, `corgano`, `csaf`, `norgano`

### `usuarios`  ·  14 refs  ·  8 archivos
- Campos observados (8): `nombre`, `no_cajero`, `lautoriza`, `clave`, `telefono`, `fecult`, `cperfil`, `fecha_modi`

### `personas`  ·  5 refs  ·  3 archivos
- Campos observados (8): `ccbucta`, `nsuccta`, `nnrocta`, `norgano`, `nentidad`, `cnombre`, `nagente`, `ccuil`

### `maestrodio`  ·  5 refs  ·  5 archivos
- Campos observados (25): `ccuil`, `capenom`, `cidcliente`, `ndoc`, `no_agente`, `fnacim`, `norgano`, `corgaorigina`, `nhaberbruto`, `domicilio`, `clasecargo`, `csexo`, `lagjs`, `ldebauto`, `fecha_actu`, `cdomicilio`, `clocalidad`, `nclacar`, `fingre`, `nsucbco`, `nctabco`, `cestciv`, `lbaja`, `fbaja`, `cbaja`

### `maemonedas`  ·  5 refs  ·  3 archivos
- Campos observados (2): `denominacion`, `codigo`

### `organismosq`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `perfiles`  ·  3 refs  ·  3 archivos
- Campos observados (1): `cdescripcion`

### `gectrldbf`  ·  3 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `parametro`  ·  2 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `programas`  ·  1 refs  ·  1 archivos
- Campos observados (1): `descripcion`

### `liqdio`  ·  1 refs  ·  1 archivos
- Campos: (no se observaron referencias `alias.campo`)


## Base: `agjsjuegos`

### `maeagencias`  ·  115 refs  ·  46 archivos
- Campos observados (25): `titular`, `cod_age`, `no_subagencia`, `no_agencia`, `no_iva`, `interior`, `fdogtia`, `ingbru`, `cbu`, `lanulada`, `cod_iva`, `calle`, `telefonos`, `ntipodoctit`, `ntipodocapo`, `no_doc`, `no_puerta`, `barrio`, `localidad`, `departamento`, `codigo_postal`, `ndocapo`, `ndoctit`, `cingbru`, `tipo_doc`

### `liquidaciones`  ·  32 refs  ·  10 archivos
- Campos observados (18): `no_sorteo`, `no_agencia`, `cod_juego`, `cod_agencia`, `no_subagencia`, `modalidad`, `com_agencia`, `ing_brutos`, `fdo_gtia`, `total`, `moneda`, `com_subage`, `t_com_subage`, `fecha`, `interior`, `multas`, `com_premios`, `municap`

### `maeagenciasq`  ·  16 refs  ·  7 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `jjimpjue`  ·  7 refs  ·  3 archivos
- Campos observados (21): `total`, `cod_juego`, `modalidad`, `cjuego`, `no_sorteo`, `fecha_sort`, `cod_agenci`, `no_agencia`, `interior`, `moneda`, `multas`, `com_agenci`, `fdo_gtia`, `ing_brutos`, `municap`, `ncreditosv`, `ndebitosv`, `no_recibo`, `calta`, `falta`, `fecha_vto`

### `v_liquida`  ·  4 refs  ·  2 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `maejuegos`  ·  4 refs  ·  2 archivos
- Campos observados (5): `denominacion`, `codigo`, `modalidad`, `com_agencia`, `com_subage`

### `maejugadas`  ·  3 refs  ·  2 archivos
- Campos observados (4): `fecha_sorteo`, `fecha_vto`, `no_sorteo`, `cod_juego`


## Base: `agjsmesa`

### `tramites`  ·  52 refs  ·  21 archivos
- Campos observados (14): `id_tramite`, `id_nro`, `id_ano`, `i_d`, `id_letra`, `nombre_ini`, `fecha_alta`, `id_nro_ini`, `nombre_aseg`, `destino`, `id_nro_aseg`, `estado`, `iniciador`, `id_tipo_ini`

### `pases`  ·  21 refs  ·  11 archivos
- Campos observados (10): `id_letra`, `id_nro`, `id_ano`, `id_tramite`, `fecha_pase`, `i_d`, `texto`, `falta`, `calta`, `ico`

### `tipotram`  ·  2 refs  ·  1 archivos
- Campos observados (3): `cdescripcion`, `descripcion`, `tipo`


## Base: `agjsseguros`

### `liqsegur`  ·  26 refs  ·  13 archivos
- Campos observados (9): `cuil`, `d_sc`, `d_svca`, `d_svco`, `d_ss`, `nro_agente`, `codorigen`, `codigo`, `claseycar`

### `titulares`  ·  19 refs  ·  11 archivos
- Campos observados (10): `cuil`, `no_doc`, `fecha_nacim`, `tipo_doc`, `no_agente`, `domicilio`, `localidad`, `beneficio`, `tipo_titular`, `dbf`

### `benefici`  ·  10 refs  ·  5 archivos
- Campos observados (11): `documento`, `nombre`, `domicilio`, `fichanro`, `fichero`, `cajon`, `grupo`, `fecha_naci`, `cuil_docu`, `codigo`, `dbf`

### `seguros`  ·  8 refs  ·  6 archivos
- Campos observados (9): `codigo`, `no_agente`, `cuil`, `estado`, `no_poliza`, `fecha`, `baja`, `fecha_modi`, `dbf`

### `liquid_dat`  ·  5 refs  ·  3 archivos
- Campos observados (7): `tipo_id_cobra`, `tipo_seg`, `id_letra`, `id_nro`, `id_ano`, `id_nro_aseg`, `cobra`

### `liqsegurx`  ·  5 refs  ·  3 archivos
- Campos: (no se observaron referencias `alias.campo`)


## Base: `(sin DBC identificado)`

### `olinea`  ·  650 refs  ·  15 archivos
- Campos observados (34): `cartera`, `no_linea`, `lpagintgra`, `lscig`, `capital_max`, `cuotas_cap`, `tna`, `nmora`, `tasa`, `gracia`, `gas_adm`, `gas_qeb`, `gas_sel`, `tipo_calculo`, `denominacion`, `nvalqueb`, `moneda`, `nhasta0`, `ngori`, `nvalggaa`, `lbonifica`, `nhasta1`, `lgoripor`, `livaori`, `livaqeb`, `livaadm`, `nbonif0`, `nbonif1`, `nbonif2`, `cft`, `npor_apor1`, `bonif0`, `bonif1`, `bonif2`

### `arial`  ·  316 refs  ·  279 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `creditos`  ·  228 refs  ·  48 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `lanulada`  ·  227 refs  ·  54 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `lrevertida`  ·  118 refs  ·  36 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `pagado`  ·  116 refs  ·  64 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `lsalir`  ·  41 refs  ·  33 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `autopp`  ·  32 refs  ·  8 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `frm31530consenvios`  ·  31 refs  ·  2 archivos
- Campos observados (2): `grid1`, `grid2`

### `tipotramite`  ·  30 refs  ·  8 archivos
- Campos observados (3): `cdescripcion`, `codigop`, `etabla`

### `beneficiarios`  ·  29 refs  ·  7 archivos
- Campos observados (7): `nombre`, `fec_res`, `nro_res`, `tipo_res`, `nro_doc`, `tipo_doc`, `tipo_bene`

### `oficinas`  ·  28 refs  ·  8 archivos
- Campos observados (12): `denominacion`, `cdescripcion`, `id_oficina`, `ecodigo`, `departamento`, `division`, `codigo`, `etabla`, `cvalor`, `lvalor`, `te_interno`, `te_linea`

### `server2`  ·  28 refs  ·  13 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `osolicitud`  ·  26 refs  ·  23 archivos
- Campos observados (175): `montosol`, `importepp`, `no_solicitud`, `no_credpp`, `ga_apenom`, `linea`, `ga_dni`, `ga_cuil`, `ga_organo`, `ga_depto`, `g2_cuil`, `ga_sueldo`, `ga_agente`, `tna`, `g3_cuil`, `ga_domicilio`, `ga_localidad`, `ga_idcli`, `ga_cbucta`, `estado`, `debauto`, `ga_cuenta`, `ga_sexo`, `intcta`, `ga_sucursal`, `g2_organo`, `g3_organo`, `ngseg`, `ngadm`, `g2_apenom`, `g3_apenom`, `ntipoggaa`, `ga_capre`, `tipo_solicitante`, `g4_cuil`, `ga_cpa`, `ga_telefono`, `cancelada`, `g2_dni`, `ga_barrio`

### `ofi_actual`  ·  26 refs  ·  6 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `aliquidar`  ·  24 refs  ·  10 archivos
- Campos observados (19): `ncred`, `nanticipo`, `cuil`, `capenom`, `ncapital`, `npzocap`, `nsaldo`, `nlinea`, `ngastosori`, `nivago`, `nsellado`, `nquebranto`, `nivaqo`, `ngastosadm`, `nivaga`, `nlote`, `linea`, `ntotal_anticipos`, `no_aporte`

### `server1`  ·  24 refs  ·  9 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `indexseek`  ·  20 refs  ·  10 archivos
- Campos: (no se observaron referencias `alias.campo`)

### `lolineanueva`  ·  20 refs  ·  4 archivos
- Campos observados (3): `cartera`, `no_linea`, `denominacion`

### `interior`  ·  20 refs  ·  4 archivos
- Campos observados (1): `color`

### `local_linea`  ·  18 refs  ·  8 archivos
- Campos observados (10): `tipo_calculo`, `lpagintgra`, `no_linea`, `cartera`, `nvalggaa`, `nvalqueb`, `tasa`, `livasint`, `lscig`, `tna`

### `frmsolcre`  ·  18 refs  ·  1 archivos
- Campos observados (3): `grd_solicitudes`, `grid1`, `infosalud`

### `recleg`  ·  14 refs  ·  11 archivos
- Campos observados (18): `norgano`, `nagente`, `n153`, `cdio`, `nclacar`, `cuil`, `nimporte`, `n811`, `ncredito1`, `ncuota1`, `ncredito2`, `ncuota2`, `ncredito3`, `ncuota3`, `ncredito4`, `ncuota4`, `ncredito5`, `ncuota5`

### `bancos`  ·  13 refs  ·  3 archivos
- Campos observados (4): `cdescripcion`, `ecodigo`, `etabla`, `cvalor`

### `sol`  ·  8 refs  ·  6 archivos
- Campos observados (54): `linea`, `no_solicitud`, `fecha_soli`, `montosol`, `cant_cuotas`, `estado`, `tasa`, `ga_apenom`, `ga_cuil`, `diferencia`, `gasista_nomb`, `cuit_cuil`, `cod_inst`, `nom_inst`, `intcta`, `iquebranto`, `isellado`, `g2_cuil`, `g2_apenom`, `g3_cuil`, `g3_apenom`, `g4_cuil`, `g4_apenom`, `tna`, `no_resol`, `fecha_resol`, `no_op`, `fecha_op`, `fecha_pago`, `capcta`, `lanulada`, `nigori`, `nivaqeb`, `nivaori`, `nivasel`, `debauto`, `igastos`, `no_liquida`, `fecha_liquida`, `no_recibo`

### `t_liq`  ·  8 refs  ·  8 archivos
- Campos observados (3): `cod_agencia`, `importe`, `total_gral`

### `proveedores`  ·  8 refs  ·  2 archivos
- Campos observados (11): `cuit`, `crazonsoc`, `contacto`, `ctipoiva`, `nprovincia`, `nproveedor`, `lanulado`, `cdomicilio`, `clocalidad`, `cdepto`, `niibb`

### `solid`  ·  6 refs  ·  6 archivos
- Campos observados (37): `no_solicitud`, `linea`, `fecha_soli`, `ga_cuil`, `ga_apenom`, `ga_agente`, `ga_organo`, `g2_cuil`, `g2_apenom`, `g2_agente`, `g2_organo`, `g3_cuil`, `g3_apenom`, `g3_agente`, `g3_organo`, `no_credpp`, `importepp`, `no_resol`, `fecha_resol`, `igastos`, `no_op`, `fecha_op`, `isellado`, `iquebranto`, `nivaqeb`, `nigori`, `nivaori`, `no_liquida`, `no_cheque`, `no_recibo`, `fecha_pago`, `montosol`, `tna`, `tasa`, `capcta`, `intcta`, `debauto`

### `maeid`  ·  6 refs  ·  6 archivos
- Campos observados (2): `no_credito`, `no_cuota`

### `linid`  ·  6 refs  ·  6 archivos
- Campos observados (3): `denominacion`, `ctactble`, `no_linea`

### `paramfer`  ·  6 refs  ·  4 archivos
- Campos observados (4): `fecha`, `feriado`, `feriadon`, `domingo`

### `situa_cr`  ·  6 refs  ·  6 archivos
- Campos observados (7): `cusuario`, `nsituacion`, `fecha_situa`, `coficina`, `fresolucion`, `nresolucion`, `ctexto`

### `resol`  ·  6 refs  ·  2 archivos
- Campos observados (15): `nro_res`, `fec_res`, `texto`, `id_letra`, `id_nro`, `id_ano`, `importe`, `nro_real`, `fec_real`, `i_d`, `id_tramite`, `cod_mot`, `tipo_res`, `modi_fecha`, `modi_usuario`

### `ofi_origen`  ·  6 refs  ·  4 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `ofi_destino`  ·  6 refs  ·  4 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `rtf`  ·  6 refs  ·  4 archivos
- Campos observados (4): `modelo`, `des_mod`, `cod_mod`, `tipo_res`

### `capresca`  ·  6 refs  ·  2 archivos
- Campos observados (2): `catamarca`, `bmp`

### `copy`  ·  5 refs  ·  3 archivos
- Campos observados (2): `bmp`, `ico`

### `libretas`  ·  4 refs  ·  4 archivos
- Campos observados (7): `lenuso`, `fcarga`, `ncanche`, `ninicial`, `ncuenta`, `lanula`, `nbanco`

### `ccvh`  ·  4 refs  ·  2 archivos
- Campos observados (17): `no_credito`, `no_aporte`, `ntipo_res`, `fec_res`, `nro_res`, `no_op`, `fecha_op`, `nanticipo`, `nsaldo`, `lpagado`, `fmodi`, `cmodi`, `fecha`, `no_liquida`, `ncapital`, `falta`, `calta`

### `tipoiva`  ·  4 refs  ·  2 archivos
- Campos observados (4): `cdescripcion`, `cvalor`, `etabla`, `codigop`

### `provincias`  ·  4 refs  ·  2 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `oec`  ·  4 refs  ·  2 archivos
- Campos observados (8): `cuota`, `mes`, `ncuotaos`, `dh_nombre`, `dh_cuil`, `nombre`, `cuil`, `derecho_ha`

### `coddto`  ·  4 refs  ·  2 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `parte1`  ·  4 refs  ·  4 archivos
- Campos observados (5): `id_tramite`, `id_letra`, `id_nro`, `id_ano`, `i_d`

### `parte2`  ·  4 refs  ·  4 archivos
- Campos observados (2): `destino`, `id_tramite`

### `parte3`  ·  4 refs  ·  4 archivos
- Campos observados (3): `id_tramite`, `id_nro`, `id_letra`

### `solgas`  ·  3 refs  ·  3 archivos
- Campos observados (10): `no_solicitud`, `cuit_cuil`, `fecha_soli`, `cant_cuotas`, `montosol`, `nigori`, `iquebranto`, `nivags`, `isellado`, `gasista_nomb`

### `v_liq_datos`  ·  3 refs  ·  1 archivos
- Campos observados (24): `cobra`, `nota`, `cant_cuotas`, `domicilio`, `liquidada`, `tipo_seg`, `beneficiario`, `monto`, `mont_cuota`, `tipo_res`, `caracter_d`, `capital`, `encond_de`, `fecha_fall`, `ctipo_seguro`, `fojas`, `fecha_liq`, `ctipo_doc`, `cdesred`, `cdescripcion`, `id_letra`, `id_nro`, `id_ano`, `tipo_id_cobra`

### `dbcursor`  ·  2 refs  ·  2 archivos
- Campos observados (3): `cursor`, `log`, `tabla`

### `paramseg`  ·  2 refs  ·  1 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `sol_activas`  ·  2 refs  ·  2 archivos
- Campos observados (13): `montosol`, `no_solicitud`, `cartera`, `linea`, `denominacion`, `diferencia`, `fecha_soli`, `no_resol`, `no_credpp`, `npor_apor1`, `fecha_resol`, `importepp`, `ncan_apor`

### `maeop`  ·  2 refs  ·  2 archivos
- Campos observados (35): `nsaldo`, `fvigencia`, `csistema`, `ntr`, `nop`, `nimporte`, `fechaop`, `lcancelada`, `nres1`, `fres1`, `nres2`, `fres2`, `lhabilitada`, `nres3`, `fres3`, `nres4`, `fres4`, `nres5`, `fres5`, `nres6`, `fres6`, `nres7`, `fres7`, `nres8`, `fres8`, `nres9`, `fres9`, `nres10`, `fres10`, `csis`, `nimpusa`, `nres`, `fres`, `nresc`, `fresc`

### `v_marca`  ·  2 refs  ·  2 archivos
- Campos observados (7): `nroleg`, `capenom`, `cturno`, `choraing`, `choraegr`, `chorasturno`, `lsabados`

### `option5`  ·  2 refs  ·  2 archivos
- Campos observados (3): `lostfocus`, `gotfocus`, `backstyle`

### `ttmp`  ·  2 refs  ·  2 archivos
- Campos observados (5): `dbf`, `no_iva`, `ncodafip`, `com_agenci`, `com_subage`

### `lin`  ·  2 refs  ·  2 archivos
- Campos observados (5): `cartera`, `no_linea`, `denominacion`, `nmoradia`, `ctactble`

### `ctrlage`  ·  2 refs  ·  2 archivos
- Campos observados (2): `no_agencia`, `cod_age`

### `command4`  ·  2 refs  ·  2 archivos
- Campos observados (24): `click`, `cancel`, `clicky`, `click5`, `clickb`, `clickp`, `click7`, `click9`, `click6`, `clicki`, `clickt`, `click_`, `clickh`, `click2`, `clicks`, `clickn`, `click1`, `clickm`, `clicku`, `clickf`, `clickc`, `clickg`, `clickr`, `clickj`

### `cps`  ·  2 refs  ·  2 archivos
- Campos observados (2): `linea`, `cartera`

### `cpg`  ·  2 refs  ·  2 archivos
- Campos observados (2): `linea`, `cartera`

### `recibidos`  ·  2 refs  ·  2 archivos
- Campos observados (11): `nnocredito`, `norgano`, `cperiodo`, `corga`, `nagente`, `ccuil`, `capenom`, `nimpdesc`, `ncuota`, `ccuotas`, `fechapago`

### `tipo_ingreso`  ·  2 refs  ·  1 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `solprn`  ·  2 refs  ·  1 archivos
- Campos observados (134): `montosol`, `ga_apenom`, `ga_dni`, `no_solicitud`, `linea`, `ga_organo`, `ga_depto`, `ga_domicilio`, `ga_localidad`, `intcta`, `ngseg`, `ngadm`, `ga_cuil`, `ga_agente`, `estado`, `capcta`, `debauto`, `fecha_soli`, `g2_cuil`, `g3_cuil`, `g4_cuil`, `ga_idcli`, `g2_organo`, `g3_organo`, `g4_organo`, `ga_cbucta`, `g2_apenom`, `g3_apenom`, `g4_apenom`, `ga_cpa`, `ga_telefono`, `ga_cuenta`, `g2_domicilio`, `g2_localidad`, `g2_depto`, `g3_domicilio`, `g3_localidad`, `g3_depto`, `g4_domicilio`, `g4_localidad`

### `codorgagap`  ·  2 refs  ·  1 archivos
- Campos observados (2): `denomina`, `codigo`

### `maepremios`  ·  2 refs  ·  2 archivos
- Campos observados (11): `njuego`, `nmodalidad`, `nsorteo`, `fsorteo`, `nagencia`, `nsubage`, `ncupon`, `npremio`, `fpago`, `fcaduca`, `ncodage`

### `command3`  ·  2 refs  ·  2 archivos
- Campos observados (29): `click`, `cancel`, `init`, `clickq`, `clickc`, `clickj`, `clickv`, `clickb`, `clickt`, `clicko`, `clickp`, `clickx`, `click5`, `clicku`, `clickr`, `clickg`, `clicky`, `clickz`, `click0`, `clickn`, `initef`, `clickaj`, `clickw`, `clickm`, `clicke`, `clickd`, `inits`, `clicks`, `clickl`

### `parte4`  ·  2 refs  ·  2 archivos
- Campos observados (3): `id_tramite`, `id_nro`, `id_letra`

### `crorig`  ·  2 refs  ·  2 archivos
- Campos observados (7): `cubica`, `no_solicitud`, `fecha_ubi`, `fecha_soli`, `ga_cuil`, `ga_apenom`, `estado`

### `ctrlenv`  ·  2 refs  ·  1 archivos
- Campos observados (5): `importe`, `ncuota`, `credito`, `cuil`, `dio`

### `tipo_ingresos`  ·  2 refs  ·  1 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `hmc`  ·  2 refs  ·  2 archivos
- Campos observados (37): `fecha_vto`, `no_credito`, `fecha_pago`, `no_cuota`, `nitna`, `capital`, `interes`, `iva_interes`, `ngseg`, `nivaseg`, `ngadm`, `nivaadm`, `total`, `interes_puni`, `iva_puni`, `interes_resar`, `iva_resar`, `total_vdo`, `total_pagado`, `estado`, `lbaja`, `fecha_alta`, `fecha_modi`, `fecha_envio`, `fecbaja`, `nipuni`, `niresa`, `gaadm_no_d`, `iva_ad_no_d`, `nrecibo`, `cobra`, `no_envio`, `cmotbaja`, `cvarios1`, `cvarios2`, `int_no_dev`, `ivai_no_dev`

### `paramdoc`  ·  1 refs  ·  1 archivos
- Campos observados (4): `cdesred`, `ecodigo`, `cdescripcion`, `etabla`

### `listbaritems`  ·  1 refs  ·  1 archivos
- Campos observados (3): `itemname`, `itemindex`, `dbf`

### `tipo_tramite`  ·  1 refs  ·  1 archivos
- Campos observados (2): `cdescripcion`, `codigop`

### `v_beneficiarios`  ·  1 refs  ·  1 archivos
- Campos observados (10): `documento`, `nombre`, `fecha_naci`, `domicilio`, `fichanro`, `codigo`, `fichero`, `cajon`, `grupo`, `cdescripcion`

### `nro`  ·  1 refs  ·  1 archivos
- Campos observados (2): `doc`, `cuil`

### `tipodoc`  ·  1 refs  ·  1 archivos
- Campos observados (4): `cdesred`, `cdescripcion`, `etabla`, `ecodigo`

### `tipo_seguro`  ·  1 refs  ·  1 archivos
- Campos observados (3): `cdescripcion`, `ecodigo`, `etabla`

### `tipo_egresos`  ·  1 refs  ·  1 archivos
- Campos observados (3): `cdescripcion`, `etabla`, `ecodigo`

### `caducos`  ·  1 refs  ·  1 archivos
- Campos observados (5): `nmes`, `nano`, `nimporte`, `lpagado`, `ncanemp`

### `foxydb`  ·  1 refs  ·  1 archivos
- Campos observados (6): `connect`, `connected`, `dbf`, `driver_mysql_53`, `base`, `motordb`


## Alias con campos pero sin tabla resuelta (posibles vistas, cursores persistentes o alias renombrados)

- **`formset`**: `form2`, `form1`, `form3`, `form4`, `form5`, `frm2510aplicaj`, `frm12005resoluciones`, `frmpagprov2`, `form6`, `frmlicita2`, `frmpagprov1`, `form7`, `frm42010pagajuex`, `frmlicita1`, `frmpagprov3`, `frm905350000abmenu`
- **`form1`**: `grid1`, `container1`, `grid2`, `documentacion`, `grid3`, `grdv_cuotas`, `grd_anexo`, `container2`, `container3`, `grdv_anex_res_g`, `grdv_anex_res`, `grdaux_egreseg`, `grdv_cred_desp`, `grd_seguros`, `grd_pagos`, `bmp`, `contitulo`
- **`command2`**: `click`, `cancel`, `clickd`, `clickg`, `init`, `clickf`, `clickw`, `clickm`, `clicku`, `clickt`, `clicks`, `clickq`, `clickh`, `clickv`, `click0`, `click7`, `click6`, `clickj`, `click5`, `clicko`, `clickk`, `clickb`, `clicky`, `click3`, `clicke`
- **`grid1`**: `column1`, `column2`, `column4`, `column3`, `column5`, `column6`, `column7`, `column8`, `column9`, `column10`, `column11`, `column12`, `column13`, `column18`, `column14`, `column15`, `column16`, `column17`, `column19`, `column20`, `column26`, `column21`, `column22`, `column23`, `column24`
- **`odio`**: `norgano`, `ccuil`, `csexo`, `no_agente`, `ntdoc`, `corgaorigina`, `capenom`, `cestciv`, `ndoc`, `nclacar`, `fnacim`, `fingre`, `nhaberbruto`, `ldebauto`, `lagjs`, `cdomicilio`, `cidcliente`, `clocalidad`, `fecha_actu`, `nctabco`, `nsucbco`, `cusuactu`
- **`command1`**: `click`, `gotfocus`, `cancel`, `clicke`
- **`page1`**: `grid1`, `grdliquid_dat`, `grdmaquinas`, `container1`, `grdexcombate`, `grd_bene_here`, `grdmovimientos`, `grdoficinas`, `txtcuil`, `txtfecha_liq`, `txtsiniestro`, `txtanio_sin`, `txtfecha_fallec`, `txtfojas`, `txtcperiodo`, `list1`, `command1`, `command2`, `deactivate`, `cbotipo_tramite`, `commandgroup1`, `cbo_organismo`, `txttotliq`, `txtlpaga`, `txtlgarantiza`
- **`page2`**: `grid1`, `beneficiarios`, `grdliquid_dat`, `grdexcombate`, `grdv_herederos`, `txtcuil`, `commandgroup1`, `list2`, `txtfecha_liq`, `txtnop`, `txttotliq`, `txtno_linea`, `txtdenominacion`, `txtcperiodo`, `txtfecha_fallec`, `txtsiniestro`, `txtanio_sin`, `cbo_organismo`, `txtfojas`, `txtfecha_soli`, `txtlinea`, `txtmontosol`, `txtno_solicitud`, `txtlpaga`, `txtlgarantiza`
- **`ocliente`**: `norgano`, `corga`, `edni`, `cidcliente`, `csexo`, `eagente`, `cdomicilio`, `cbarrio`, `clocalidad`, `cdepto`, `ccpa`, `ctelefono`, `capenom`, `fnacim`, `ccatfun`, `ffperm`, `nsueldo`, `cbenef`, `esucursal`, `ecuenta`, `ccbucta`, `ccuil`, `egarantias`, `nmontogar`, `ncancre`
- **`oo`**: `no_credpp`, `no_liquida`, `linea`, `no_solicitud`, `fecha_soli`, `importepp`, `no_resol`, `fecha_resol`, `no_op`, `fecha_op`, `fecha_liquida`, `clinea`, `cdio`, `nimporte`, `cuotas`, `ncuota`, `norgano`, `nclacar`, `nagente`, `n153`, `ncredito`, `cuil`, `codigo`, `lote`, `id_ingreso`
- **`cierrec`**: `moneda`, `total_gral`, `cod_juego`, `com_premios`, `com_agencia`, `com_subage`, `ing_brutos`, `fdo_gtia`, `intereses`, `iva`, `cheque`, `importe`, `cjuego`, `total`
- **`desp_salir1`**: `ico`
- **`asmaec`**: `ccuil`, `cidcliente`, `capenom`, `csexo`, `norgano`, `corga`, `lcapre`, `eagente`, `nsueldo`, `egarantias`, `ncancre`, `ncuotacre`, `nmontogar`, `ldebauto`, `cbenef`, `esucursal`, `ecuenta`, `ccbucta`
- **`frm3750controldio`**: `grid1`, `grid3`, `grid2`
- **`mccalcre`**: `total`, `ncapcta`, `fvto`, `nintcta`, `ngsadm`, `ncuota`, `ngsseg`, `nivaint`, `nivagsa`, `nivagss`, `ntna`, `ngori`, `ntotal`, `ngadm`, `nivaadm1`
- **`frm3730modgen`**: `grid1`, `grid3`, `grid4`
- **`ee`**: `cuil`, `ncredito`, `ncuota`, `nimporte`, `credito`, `cuota`, `norgano`, `fecha`, `nclacar`, `nagente`, `clasecargo`
- **`msol`**: `g2_idcli`, `ga_idcli`, `g2_sexo`, `ga_sexo`, `g2_organo`, `ga_organo`, `g2_orga`, `g2_agente`, `g2_catfun`, `g2_dni`, `g2_cuil`, `g2_apenom`, `g2_domicilio`, `g2_localidad`, `g2_fnacim`, `g2_fperm`, `g2_sueldo`, `g2_sucursal`, `g2_cuenta`, `ga_orga`, `ga_agente`, `ga_catfun`, `ga_dni`, `ga_cuil`, `ga_apenom`
- **`ocuota`**: `no_credito`, `no_cuota`, `total`, `total_vdo`, `fecha_vto`, `capital`, `interes`, `iva_interes`, `ngseg`, `nivaseg`, `ngadm`, `nivaadm`, `cobra`, `estado`, `nitna`, `fecha_alta`, `total_pagado`, `fecha_modi`, `interes_puni`, `interes_resar`, `iva_puni`, `iva_resar`, `fecha_pago`, `nrecibo`
- **`v_pagos`**: `no_liquida`, `no_op`, `fecha_op`, `cuil`, `fecha_liquida`, `nro_res`, `total`, `fec_res`, `importe`, `tipo_egreso`, `tipo_res`, `detalle`, `no_recibo`, `no_cheque`, `cdescripcion`, `fechapago`, `banco`, `csis_op`
- **`omaecuotas`**: `no_cuota`, `interes_puni`, `iva_puni`, `no_credito`, `fecha_vto`, `total_pagado`, `capital`, `interes`, `iva_interes`, `total_vdo`, `interes_resar`, `iva_resar`, `total`, `ngseg`, `nivaseg`, `ngadm`, `nivaadm`, `estado`, `fecha_modi`
- **`page3`**: `grid1`, `grdmantenimiento`, `txtcuil`, `grd_requisitos`, `cbo_organismo`, `cbotipo_id_iniciador`, `txtlpaga`, `txtlgarantiza`, `txtcmotbaja`, `txtnombre`, `txtso_apenom`, `txtso_fnacim`, `txtso_sexo`, `txtso_domicilio`, `txtso_barrio`, `txtso_localidad`, `txtso_depto`, `txtso_cpa`, `txtso_telefono`, `txtso_agente`, `txtso_sueldo`, `txtcorreo_electronico`, `cbo_tipo_cliente`, `txtso_cbucta`, `cbo_tramite`
- **`lcc`**: `cuil`, `cuenta`, `cbucta`, `idcli`, `dni`, `fnacim`, `domicilio`, `barrio`, `localidad`, `depto`, `cpa`, `telefono`, `catfun`, `fperm`, `benef`, `tipo_garante`, `capre`, `correo_electronico`, `mat_catastral`
- **`otramites`**: `id_tramite`, `id_ano`, `i_d`, `id_nro_aseg`, `id_tipo_ini`, `id_letra`, `id_nro`, `destino`, `id_tipo_aseg`, `id_nro_ini`, `nombre_ini`, `nombre_aseg`, `estado`, `fecha_alta`, `id_orig_letra`, `id_orig_ano`, `id_orig_nro`, `iniciador`
- **`page4`**: `grid1`, `txtcuil`, `cbo_organismo`, `txtlpaga`, `txtlgarantiza`, `txtbusca`, `txtso_apenom`, `txtso_fnacim`, `txtso_sexo`, `txtso_domicilio`, `txtso_barrio`, `txtso_localidad`, `txtso_depto`, `txtso_cpa`, `txtso_telefono`, `txtso_agente`, `txtso_sueldo`, `txtcorreo_electronico`, `cbo_tipo_cliente`, `txtso_cbucta`
- **`oegresos`**: `importe`, `nro_res`, `fec_res`, `no_credito`, `no_cheque`, `no_recibo`, `fechapago`, `fecha_op`, `no_op`, `banco`, `tipo_egreso`, `no_liquida`
- **`font`**: `bold`, `color`, `italic`
- **`desp_ok2`**: `ico`
- **`v_cobros`**: `no_liquida`, `dni`, `lrevertida`, `fecha_carga`, `cuil`, `id_ingreso`, `intereses`, `iva`, `total_gral`, `total`, `consor`, `tasa`, `fecha`, `cualcuo`, `mes`, `cheque`, `fecrev`, `cmotivorev`, `cupon`, `moncuo`, `banco`, `interes`, `ivain`, `gastos`, `nivaadm`
- **`desp_cancelar4`**: `ico`
- **`grid2`**: `column2`, `column3`, `column4`, `column1`, `column5`, `column6`, `column7`, `column8`, `column9`, `column10`, `column11`, `column12`, `column13`, `column14`, `column15`, `column16`, `column17`
- **`dtodio`**: `linea`, `cobra`, `no_credito`, `no_cuota`, `cuil`, `fecha_vto`, `total`, `capre`, `idcli`, `interes_pu`, `iva_puni`, `interes_re`, `iva_resar`, `total_vdo`, `debauto`, `denominaci`, `cartera`, `nmoradia`, `tasa`, `total_paga`, `dbf`, `estado_a`, `estado_b`, `capital`, `interes`
- **`command5`**: `click`, `cancel`, `click2`, `clickh`, `clickm`, `clickv`, `click8`, `clickk`, `clickzj`, `clickd`, `clickn`
- **`column4`**: `dynamicbackcolor`, `currentcontrol`, `check1`, `columnorder`, `fontshadow`
- **`column6`**: `dynamicbackcolor`, `currentcontrol`, `columnorder`, `fontshadow`
- **`pp`**: `dbf`, `fortal`, `g2_cuil`, `g3_cuil`, `c_juego`, `importe`, `idx`, `d_juego`, `c_codigo`, `d_codigo`, `no_credito`, `ga_organo`, `g2_organo`, `g3_organo`, `linea`, `capital`, `interes`, `iva_intere`, `total`, `interes_pu`, `interes_re`, `iva_puni`, `iva_resar`, `total_vdo`, `total_paga`
- **`column1`**: `dynamicbackcolor`, `currentcontrol`, `columnorder`, `bound`, `check1`, `container1`, `fontshadow`
- **`activecell`**: `formular1c1`
- **`oleapp`**: `cells`, `columns`
- **`modgen_egresos`**: `grid1`
