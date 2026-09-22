# Catálogo de datos REAL — backup CCyPP

> Esquema extraído de los DBF reales del backup (por módulo).


**Totales analizados:** 216 tablas · 62,595,631 registros.


## Caja — 21 tablas · 3,187,641 registros

- **`cj_liqhis`** (1,370,363 reg, 42 campos): cod_juego, modalidad, cjuego, no_sorteo, fecha_sort, cod_agenci, no_agencia, no_subagen, interior, moneda, recaudacio, premios, com_premio, multas, com_agenci, com_subage, fdo_gtia, ing_brutos, municap, ncreditosv, ndebitosv, t_com_suba
- **`cj_paghis`** (652,538 reg, 17 campos): cod_agenci, fecha_pago, origen, no_recibo, sno_recibo, bonos, pesos, total, cobrado_bo, cobrado_pe, cobrado_to, vuelto_bon, vuelto_pes, premios_pe, premios_bo, cajero, anulado
- **`cj_fpaghis`** (652,302 reg, 10 campos): no_recibo, sno_recibo, moneda, origen, fecha_pago, importe, vuelto, cheque, cajero, anulado
- **`cajaliq`** (222,616 reg, 42 campos): cod_juego, modalidad, cjuego, no_sorteo, fecha_sort, cod_agenci, no_agencia, no_subagen, interior, moneda, recaudacio, premios, com_premio, multas, com_agenci, com_subage, fdo_gtia, ing_brutos, municap, ncreditosv, ndebitosv, t_com_suba
- **`cj_crsghis`** (143,722 reg, 56 campos): norden, id_ingreso, no_liquida, dni, apenom, no_agencia, no_subagen, fecha_carg, cualcuo, moncuo, interes, ivain, nseg, nivaseg, gastos, nivaadm, total, mes, ano, codcon, consor, nbanco
- **`cierrejuegos`** (56,610 reg, 13 campos): fecha, juego, cjuego, moneda, cmoneda, d_ingresos, d_egresos, v_ingresos, v_egresos, pa_ingreso, pa_egresos, pd_ingreso, pd_egresos
- **`cajapagos`** (31,714 reg, 17 campos): cod_agenci, fecha_pago, origen, no_recibo, sno_recibo, bonos, pesos, total, cobrado_bo, cobrado_pe, cobrado_to, vuelto_bon, vuelto_pes, premios_pe, premios_bo, cajero, anulado
- **`cajaforpag`** (31,707 reg, 10 campos): no_recibo, sno_recibo, moneda, origen, fecha_pago, importe, vuelto, cheque, cajero, anulado
- **`cjcontrol`** (12,132 reg, 17 campos): nagencia, linterior, njuego, cjuego, nsorteo, fsorteo, fvto, fpago, ntotal, npremios, ntotrec, ntotrec1, nrecibo, lprocesado, lcobrado, corigen, fv
- **`cajacreseg`** (5,629 reg, 56 campos): norden, id_ingreso, no_liquida, dni, apenom, no_agencia, no_subagen, fecha_carg, cualcuo, moncuo, interes, ivain, nseg, nivaseg, gastos, nivaadm, total, mes, ano, codcon, consor, nbanco
- **`cierremoneda`** (4,806 reg, 8 campos): fecha, moneda, ingresos, egresos, efectivo, cheques, vueltos, saldo
- **`0107m`** (2,398 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`cierrecaja`** (385 reg, 14 campos): cod_juego, moneda, fecha, cajero, importe_li, cobrado_pe, cobrado_di, egresos_pe, egresos_di, pendiente_, pendiente2, egrepend_d, egrepend_p, diferencia
- **`cjcomismes`** (378 reg, 18 campos): cperiodo, nagencia, nsubage, capenom, cuit, cnroib, nrecauda, ncomision, ningbru, nbaseimpo, nretencion, nreintegro, ntributa, nrecibo, falta, calta, fmodi, cmodi
- **`0107r`** (146 reg, 7 campos): c_juego, n_agen, d_operac, importe, c_moneda, c_resumen, f_movin
- **`agenjuegos`** (140 reg, 15 campos): cod_agenci, no_agencia, no_subagen, interior, quipesos, quibonos, quiniela, quini6, loto, brinco, prode, mono, telekino, abc, resto
- **`cjcontrolt`** (32 reg, 17 campos): nagencia, linterior, njuego, cjuego, nsorteo, fsorteo, fvto, fpago, ntotal, npremios, ntotrec, ntotrec1, nrecibo, lprocesado, lcobrado, corigen, fv
- **`cajaliqdife`** (21 reg, 31 campos): cod_juego, modalidad, no_sorteo, fecha_sort, cod_agenci, no_agencia, no_subagen, interior, moneda, recaudacio, premios, com_premio, multas, com_agenci, com_subage, fdo_gtia, ing_brutos, municap, t_com_suba, total, fecha_vto, pagado
- **`agentotal`** (2 reg, 10 campos): fecha, quiniela, quini6, loto, brinco, mono, prode, telekino, abc, resto
- **`cierreuno`** (0 reg, 8 campos): cod_juego, fecha, moneda, tipo, ingresos, egresos, cobrado, saldo
- **`cjimporta`** (0 reg, 18 campos): cod_juego, modalidad, no_sorteo, fec_sorteo, no_agencia, no_subagen, moneda, recauda, premios, com_premio, multas, com_age, com_subage, fdo_gtia, ing_brutos, municap, t_com_suba, total

## Contabilidad — 23 tablas · 10,584,384 registros

- **`basectadev`** (2,575,573 reg, 52 campos): no_credito, no_cuota, fecha_vto, sdo_cap, nitna, capital, interes, iva_intere, ngseg, nivaseg, ngadm, nivaadm, total, fecha_pago, via_pago, interes_pu, iva_puni, interes_re, iva_resar, total_vdo, total_paga, saldo
- **`ctable`** (2,118,189 reg, 45 campos): no_credito, no_cuota, fecha_vto, sdo_cap, nitna, capital, interes, iva_intere, ngseg, nivaseg, ngadm, nivaadm, total, fecha_pago, nipuni, interes_pu, iva_puni, niresa, interes_re, iva_resar, total_vdo, gaadm_no_d
- **`asientos`** (2,009,400 reg, 14 campos): cuenta, ctaplan, fecha, cperio, fecpago, norden, ndebito, ncredito, nsaldo, falta, calta, fmodi, cmodi, creferenci
- **`crctacte`** (1,049,892 reg, 30 campos): cuenta, ncredito, ncuota, corga, fecvto, fechaenvio, fechapago, via_pago, ncodmov, nsigno, ndebitos, ncreditos, nsaldo, ncapital, nintnor, nivanor, ngsas, nsellado, nquebra, nintpun, nivapun, nintres
- **`partecci`** (1,029,092 reg, 15 campos): ncredito, fpago, ctactble, nrecibo, ncuota, fvto, ndiasmora, ntasamora, ncapital, nintnorm, nivanorm, nintmora, nivamora, ntotcob, cviapago
- **`crivacob`** (905,474 reg, 11 campos): fecha, cperiodo, corigen, ncartera, nlinea, nivaintnor, nivaintpun, nivaintres, nivaintmor, nivatotal, claveope
- **`cc1`** (236,583 reg, 13 campos): ctactble, ncredito, ncuota, fpago, nrecibo, capenom, fvto, ncapital, nintnorm, nivanorm, nintmora, nivamora, ntotcob
- **`ctrlenv`** (208,200 reg, 12 campos): norgano, nclacar, nagente, n811, nimporte, n153, ncredito, cuota, cuil, cespa, cfec, cfil
- **`solble`** (145,615 reg, 212 campos): no_solicit, fecha_soli, so_cuil, so_idcli, so_apenom, so_dni, so_fnacim, so_sexo, so_domicil, so_barrio, so_localid, so_depto, so_cpa, so_telefon, so_agente, so_organo, so_orga, so_capre, so_catfun, so_fperm, so_sueldo, so_benef
- **`baseopdev`** (145,320 reg, 34 campos): n_solicitu, fecha_soli, c_cuil, c_apenom, n_organo, c_orga, n_capital, n_linea, c_lindenom, c_ctactble, n_pzo_tota, n_pzo_capi, n_pzo_grac, n_gs_seg, n_gs_adm, n_gs_orig, n_iva_gsor, n_gs_sella, n_gs_queb, n_iva_gsqu, n_gastos, n_iva_gast
- **`contgral`** (106,557 reg, 35 campos): fecha, fe1, naamm, nasiento, nrecibo, ctipo, nagencia, nsubage, capenom, cdestino, corigen, nsorteo, ncuota, nperiodo, cmoneda, nimppes, nintpes, nivapes, nprepes, ntotpes, nimpbon, nintbon
- **`tempie`** (49,711 reg, 62 campos): dni, apenom, no_agencia, no_subagen, fecha_carg, cualcuo, moncuo, interes, ivain, total, mes, ano, codcon, consor, banco, cheque, cupon, fecha, tasa, recofi, sno_recibo, pagado
- **`cuotasold`** (2,557 reg, 14 campos): cod_org, cuit1, dni, cuit2, agente, apenom, monto, cualcuo, moncuo, mes, ano, cucar, quien, obse
- **`quiniela`** (378 reg, 3 campos): n1, nombre, comiage
- **`agereten`** (360 reg, 9 campos): dj_periodo, dj_present, numero, fecha, con_ibnum, bas_impo, alicuota, importe, id_estado
- **`contrib`** (360 reg, 11 campos): con_ibnum, con_cuit, nombre, direccion, telefono, loc_id, nom_loc, cod_postal, dpt_id, nom_dpt, pvc_id
- **`partecce`** (358 reg, 39 campos): ncredito, ntipoegre, fpago, nrecibo, capenom, ctactble, nlincred, ncapital, nsellos, ngsas, nseguro, ncredpp, nlineapp, nintppnoc, nivappnoc, nprevpago, ntotpag, nintfin, nivafin, ntotfin, cviapago, ctipo
- **`padron`** (324 reg, 6 campos): codigo, ag._n§, sub_ag._, titular, domicilio, cuit
- **`creditosold`** (151 reg, 28 campos): cod_cre, fecha, apellido, nombre, dni, cuit1, cuit2, agente, domi, circuito, seccion, tele, catfun, carga, cod_org, sueldo, mon_sol, mon_oto, q_car, cancelo, liqui, fec_liq
- **`agencir`** (145 reg, 28 campos): cod_age, id_age, agenpro, ageexpe, nombre_age, agedocu, agetipo, domicilio, agedomp, agetele, ageloca, garnomb, zoncodi, zontcod, agepend, sorsnli, numnume, agerete, agecuit, agenuli, ageamat, agepres
- **`agencis`** (145 reg, 28 campos): cod_age, agereal, agenpro, ageexpe, nombre_age, agedocu, agetipo, domicilio, agedomp, agetele, ageloca, garnomb, zoncodi, zontcod, agepend, sorsnli, numnume, agerete, agecuit, agenuli, ageamat, agepres
- **`ctblecred`** (0 reg, 10 campos): fechapago, capenom, ctactble, ncapital, nretsellos, nretgsas, nretqueb, nliqpag, ninttotfin, nimprecup
- **`transacc`** (0 reg, 10 campos): ctactble, fecha, corigen, idtransac, fperiodo, norganismo, nsaf, ncreditos, ndebitos, nsaldo

## Creditos — 45 tablas · 19,607,021 registros

- **`recibidos`** (4,771,255 reg, 13 campos): norgano, corga, nclacar, nagente, ccuil, capenom, nimpdesc, nnocredito, ccuotas, ncuota, cperiodo, lbonos, fechapago
- **`envios`** (4,543,377 reg, 37 campos): no_cred, linea, no_cuota, no_agente, no_cuil, apenom, sexo, organo, orga, fecha_vto, capital, interes, iva_inte, ngseg, nivaseg, ngadm, nivaadm, total, int_puni, iva_puni, int_resar, iva_resar
- **`tabla_fox`** (2,394,961 reg, 26 campos): no_credito, no_cuota, fecha_vto, fecha_pago, saldo, via_pago, estado_a, cobra, fecha_envi, no_envio, fecha_soli, so_cuil, so_idcli, so_apenom, so_dni, so_organo, so_orga, ga_cuil, ga_idcli, ga_apenom, ga_dni, ga_organo
- **`maecuotas`** (2,118,211 reg, 48 campos): no_credito, no_cuota, fecha_vto, sdo_cap, nitna, capital, interes, iva_intere, ngseg, nivaseg, ngadm, nivaadm, total, fecha_pago, nipuni, interes_pu, iva_puni, niresa, interes_re, iva_resar, total_vdo, gaadm_no_d
- **`maecuotas_linea`** (2,118,159 reg, 49 campos): no_credito, no_cuota, fecha_vto, sdo_cap, nitna, capital, interes, iva_intere, ngseg, nivaseg, ngadm, nivaadm, total, fecha_pago, nipuni, interes_pu, iva_puni, niresa, interes_re, iva_resar, total_vdo, gaadm_no_d
- **`himaecuotas`** (1,754,008 reg, 45 campos): no_credito, no_cuota, fecha_vto, sdo_cap, nitna, capital, interes, iva_intere, ngseg, nivaseg, ngadm, nivaadm, total, fecha_pago, nipuni, interes_pu, iva_puni, niresa, interes_re, iva_resar, total_vdo, gaadm_no_d
- **`ctacte`** (1,581,303 reg, 25 campos): ccuil, nno_credit, nno_cuota, nno_liquid, nno_recibo, tfecha, ncodmov, ndebcre, ndebitos, ncreditos, lcontra, ctipo, ncapital, ninteres, niva, nint_puni, niva_puni, nint_resar, niva_resar, alta_fecha, alta_usuar, modi_fecha
- **`maeclientes`** (78,561 reg, 39 campos): cidcliente, ccuil, capenom, edni, fnacim, csexo, cdomicilio, cbarrio, clocalidad, cdepto, ccpa, ctelefono, cemail, eagente, norgano, corga, ntipocli, cbenef, lcapre, ncatfun, ccatfun, ffperm
- **`solicitud`** (78,447 reg, 215 campos): no_solicit, fecha_soli, so_cuil, so_idcli, so_apenom, so_dni, so_fnacim, so_sexo, so_domicil, so_barrio, so_localid, so_depto, so_cpa, so_telefon, so_agente, so_organo, so_orga, so_capre, so_catfun, so_fperm, so_sueldo, so_benef
- **`hisolicitud`** (67,169 reg, 212 campos): no_solicit, fecha_soli, so_cuil, so_idcli, so_apenom, so_dni, so_fnacim, so_sexo, so_domicil, so_barrio, so_localid, so_depto, so_cpa, so_telefon, so_agente, so_organo, so_orga, so_capre, so_catfun, so_fperm, so_sueldo, so_benef
- **`turnos`** (38,548 reg, 24 campos): ctipo, nturno, periodo, fecha, norden, cuilsol, cidsol, capenoms, cdomicilio, clocalidad, csexo, nlinea, nsueldos, nmargens, norganos, nagentes, lvigente, lusado, lautoriza, uautoriza, falta, calta
- **`env_aud`** (27,138 reg, 12 campos): nocredito, fechalta, cuil, capenom, nmonto, fechaenvio, cestado, cubica, calta, falta, cmodi, fmodi
- **`jub_ctas`** (11,873 reg, 18 campos): no_solicit, cuil, no_cuota, valor_cta, fecha_vto, pagada, fecha_pago, usuario_pa, no_resoluc, fecha_reso, no_op, fecha_op, codban, no_cheque, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`bus_cred`** (9,961 reg, 11 campos): no_solicit, fecha_soli, no_linea, denominaci, monto_soli, cant_cuota, cuota, estado, cuil, tipo, nombre
- **`crcliact`** (4,548 reg, 46 campos): nocred, fecha, cuil, cidcli, nagente, csexo, norgano, corga, lagjs, lgarcapre, nhaberes, nlinea, ncartera, caracter, npzotot, npzogar, lmora, cestado, ldebauto, nctaact, nimpact, nctabaj
- **`prodcuotas`** (3,522 reg, 30 campos): esolicitud, ncuota, fvencimien, nsaldo, namortiza, ninteres, niva, ntotal, fpervto, nperamo, nperint, nperiva, npertot, cestado, caqc, fenvio, fpago, cmediopago, erecibo, cusupago, npago, nsaldocta
- **`sol_jubi`** (2,210 reg, 23 campos): no_solicit, no_benefic, cuil, ape_nom, domicilio, localidad, depto, telefono, expediente, baja_mes, haberes, monto, cuotas, liquidada, fecha_alta, usuario_al, fecha_modi, usuario_mo, no_resoluc, fecha_reso, prorroga, nroprorrog
- **`enviospat`** (818 reg, 31 campos): ctipregpat, cperiodopa, corganopat, cuentapat, cuilpat, ctaclipat, capenompat, nocredpat, nocuotapat, nimportepa, no_cred, linea, no_agente, sexo, organo, orga, fecha_vto, total, total_vdo, fecha_pago, fecha_envi, lenvio
- **`ee`** (704 reg, 14 campos): organo, clasecargo, agente, codigo, importe, codigo153, credito, cuotas, cuil, espacios, fecha, dio, saldo, consorcio
- **`turnosnew`** (500 reg, 17 campos): canomes, nturno, fecha, norden, cuil, capenom, csexo, nagente, norgano, corga, cidcliente, lactivo, lanulado, falta, calta, fmodi, cmodi
- **`cr_hisclin`** (424 reg, 26 campos): id, cuil, capenom, cdomicilio, cbarrio, clocalidad, cdepto, cpostal, fnacim, nedad, ctelefono, cemail, ngrupofam, csituafam, lviv_prop, norganismo, m_motivo, m_evalua, m_docum, lusada, ncredito, cargador
- **`turnodia`** (420 reg, 11 campos): ctipo, fecha, lhabilitad, cdiasem, ndesde, nhasta, nlibres, falta, calta, fmodi, cmodi
- **`lineacred`** (402 reg, 57 campos): no_linea, denominaci, cartera, lhabilitad, cupo, capital_ma, por_afecta, cuotas_cap, gracia, cuotas_int, ncan_apor, lpagintgra, lscig, tasa, tna, lbonifica, nbonif0, nhasta0, nbonif1, nhasta1, nbonif2, nmora
- **`datadict`** (325 reg, 21 campos): moduledscr, dbasename, dbf_name, descript, field_num, field_name, field_type, field_len, field_dec, alnull, frule, f_mess, defvalue, prim_key, uniq_key, refftable, refffield, specdiscr, is_db, dbtype, spec_type
- **`prodsolicitud`** (47 reg, 51 campos): eidsolicit, ffecha, cso_cuil, cso_idcli, nso_agente, nso_organo, nso_sueldo, cga1_cuil, cga1_idcli, nga1_agent, nga1_organ, nga1_sueld, cga2_cuil, cga2_idcli, nga2_agent, nga2_organ, nga2_sueld, cga3_cuil, cga3_idcli, nga3_agent, nga3_organ, nga3_sueld
- **`crgasistas`** (37 reg, 13 campos): id, tipo, cuit, capenom, nmatricula, cdomicilio, cbarrio, clocalidad, ctelefonos, falta, calta, fmodi, cmodi
- **`cr_monto_max`** (29 reg, 9 campos): cperiodo, cgrupo, nimporte, nusado, lvigente, falta, calta, fmodi, cmodi
- **`paramcred`** (27 reg, 12 campos): tabla, denominaci, no_paramet, par_denom1, par_denom2, par_valor1, par_valor2, par_logico, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`c_areimp`** (23 reg, 16 campos): tipo_egres, sub_tipo, no_liquida, fecha_liqu, lote, tipo_res, nro_res, fec_res, no_credito, apenom, cuil, importe, no_op, fecha_op, reimp, _nullflags
- **`apis`** (4 reg, 8 campos): nombre, url, client_id, client_sec, grant_typ, fecha, token, metodo
- **`foxuser`** (3 reg, 7 campos): type, id, name, readonly, ckval, data, updated
- **`enti_solicitud`** (3 reg, 23 campos): ncodenti, ncredito, nsolicitud, fsolicitud, cuil, capenom, nagente, corga, norgano, cidcliente, nhaberes, nlinea, nplazo, ncapital, cestado, lpagado, fechapago, lanulado, fechanula, cusuanula, cmotivo, fmodi
- **`tipocalculo`** (3 reg, 6 campos): tipo, denominaci, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`gtia_hipo_prda`** (1 reg, 17 campos): id, nsolicitud, ctipogar, nformulari, nregsec, finscripci, cdominio, nmat_cat_i, ntestimoni, cuit_escri, cnom_escri, cuit_titu, cnom_titu, falta, calta, fmodi, cmodi
- **`prodclientes`** (0 reg, 20 campos): ccuil, capenom, cdomicilio, clocalidad, ccodpos, cdepartame, ntipdoc, csexo, cestciv, fnacimient, ncreditos, nmontocre, ngarantias, nmntogar, esucursal, ncuenta, falta, fusualta, fmodi, fusumodi
- **`carteras`** (0 reg, 7 campos): no_cartera, denominaci, cta_contab, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`ccvh`** (0 reg, 18 campos): id, no_credito, no_aporte, fecha, no_liquida, ntipo_res, nro_res, fec_res, no_op, fecha_op, ncapital, nanticipo, nsaldo, lpagado, falta, calta, fmodi, cmodi
- **`enti_cuotas`** (0 reg, 18 campos): nsolicitud, ncuota, fvencimien, cestado, ncapital, ninteres, nivaint, ngastos, nivagas, ntotalcuot, frecepcion, fenvio, cfilenv, frecibido, fpago, cusupago, fmodi, cmodi
- **`enviopat`** (0 reg, 38 campos): no_soli, no_cred, linea, no_cuota, no_agente, no_cuil, apenom, sexo, organo, orga, fecha_vto, capital, interes, iva_inte, ngseg, nivaseg, ngadm, nivaadm, total, int_puni, iva_puni, int_resar
- **`fometuri`** (0 reg, 15 campos): nsolicitud, cidcli, capenom, falta, cusualta, nvoucher, fecvou, nimporte, cprestador, liquidado, nliquida, fliquida, cusuliq, fmodi, cmodi
- **`maesubsidios`** (0 reg, 23 campos): enosub, ffecha, ccuil, elinea, nmonto, ecuotas, nresolucio, fresolucio, eop, fop, eliquida, fliquida, erecibo, ebanco, ncheque, cestado, fpago, cusupago, lpagado, falta, cusualta, fmodi
- **`requisitos`** (0 reg, 6 campos): linea, datos, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`situa_cr`** (0 reg, 13 campos): id, nsolicitud, nsituacion, fecha_situ, coficina, cusuario, nresolucio, fresolucio, ctexto, falta, calta, fmodi, cmodi
- **`ssliq`** (0 reg, 16 campos): nidss, nliquida, fliquida, npago, nrorespago, fecrespago, nroop, fecop, nimporte, lpago, fpago, cusuliq, norecibo, cajero, calta, falta
- **`ssmae`** (0 reg, 13 campos): nidss, fecha, nlinea, cuilclie, cuilcobra, nmonto, ncanpagos, nporpripag, nroresoto, fecresoto, cestado, calta, falta

## Despacho — 3 tablas · 211,928 registros

- **`beneficiarios`** (158,477 reg, 18 campos): nro_res, fec_res, tipo_res, id_tramite, id_letra, id_nro, id_ano, i_d, tipo_doc, nro_doc, nombre, tipo_bene, alta_fecha, alta_usuar, modi_fecha, modi_usuar, lanulado, fanula
- **`resoluciones`** (53,088 reg, 25 campos): id, nro_res, fec_res, tipo_res, nro_real, fec_real, id_tramite, id_letra, id_nro, id_ano, i_d, importe, cod_mot, texto, usado, nro_op, fec_op, alta_usuar, alta_fecha, modi_usuar, modi_fecha, disposicio
- **`rtf`** (363 reg, 10 campos): tipo_res, cod_mod, des_mod, modelo, alta_usuar, alta_fecha, modi_usuar, modi_fecha, disposicio, seguros

## Egresos — 9 tablas · 451,344 registros

- **`egresos`** (340,733 reg, 53 campos): tipo_egres, sub_tipo, no_liquida, fecha_liqu, tipo_res, nro_res, fec_res, id_tramite, id_letra, id_nro, id_ano, i_d, no_credito, no_solicit, apenom, cuil, cnrofac, cnrorec, detalle, no_op, fecha_op, csis_op
- **`cheques`** (73,276 reg, 19 campos): nbanco, ncuenta, cuenta, ncheque, fecha, nimporte, nop, fop, nres, fres, nliqui, fliqui, falta, calta, fmodi, cmodi, lanula, fanula, canula
- **`maeop`** (35,096 reg, 39 campos): nop, fechaop, fvigencia, nimporte, ntr, nres1, fres1, nres2, fres2, nres3, fres3, nres4, fres4, nres5, fres5, nres6, fres6, nres7, fres7, nres8, fres8, nres9
- **`libretas`** (2,003 reg, 14 campos): nbanco, ncuenta, cuenta, fcarga, ncanche, ninicial, lenuso, falta, calta, fmodi, cmodi, lanula, fanula, canula
- **`tmplis`** (120 reg, 12 campos): tipoegre, subtipo, sistema, no_op, fec_op, beneficiar, dni, concepto, importe, fec_pago, no_recibo, no_cheque
- **`lotesib`** (74 reg, 8 campos): id, corigen, nregistros, ntransfer, lgenerado, ltransfer, falta, calta
- **`paramegre`** (25 reg, 13 campos): id_tabla, denomina, codigo, descripcio, valor1, valor2, valor3, valor4, fecha_alta, usuario_al, fecha_modi, usuario_mo, ca
- **`transfer`** (9 reg, 16 campos): ncuenta, tid_transa, ffecpres, ffecacre, nent_acred, nsuc_acred, ndig_verif, ncbu_acred, nimporte, creferenci, cidcliente, nclase_doc, ntipo_doc, nnro_doc, nestado, cdatos_emp
- **`acegresos`** (8 reg, 7 campos): source, data, count, weight, created, updated, user

## General — 41 tablas · 7,799,194 registros

- **`auditoria`** (6,486,913 reg, 8 campos): hora_event, maquina, usuario, cautoriza, csistema, cperfil, proceso, opcion
- **`hisaudi`** (612,279 reg, 5 campos): hora_event, maquina, usuario, proceso, opcion
- **`maedio`** (237,814 reg, 29 campos): no_agente, tdoc, ndoc, cuil, ccuil, cidcliente, apenom, organismo, organo, clasecargo, haberbruto, sexo, sexoa, antiguedad, domicilio, fnacim, fingre, estciv, profesion, localidad, departamen, categ
- **`padronelectoral`** (219,758 reg, 14 campos): nrodoc, ctipdoc, ccuil, nano, csexo, capellido, cnombres, cprofesion, no1, no2, cdomicilio, nro, c1, c2
- **`maestrodio`** (75,457 reg, 27 campos): cidcliente, norgano, corgaorigi, no_agente, nclacar, ntdoc, ndoc, csexo, ccuil, capenom, cdomicilio, clocalidad, fnacim, fingre, cestciv, nhaberbrut, nsucbco, nctabco, ldebauto, lagjs, fecha_actu, cusuactu
- **`personas`** (52,379 reg, 8 campos): ccuil, cnombre, nagente, norgano, nsuccta, nnrocta, nentidad, ccbucta
- **`liqdio`** (30,206 reg, 16 campos): organo, clasecargo, no_agente, apenom, tipdoc, no_doc, cuil, haberesca, haberessa, descuentos, neto, seg_obli, seg_sepe, seg_cony, seg_adi1, seg_adi2
- **`aux_egreseg`** (18,856 reg, 10 campos): tipo, resolucion, fec_resolu, tipo_seg, beneficiar, dni_asegur, monto, fecha_alta, fecha_pago, pagada
- **`maediofil`** (15,744 reg, 15 campos): nagente, ntdoc, ndoc, ncuil, capenom, norgano, nclacar, nsueldo, nsexo, nantig, cdomicilio, nfecnac, nfecing, nestciv, nprofe
- **`mde`** (12,028 reg, 26 campos): no_agente, noag1, noag2, tdoc, ndoc, cuil, ccuil, apenom, organismo, organo, clasecargo, haberbruto, sexo, antiguedad, domicilio, fnacim, fingre, estciv, profesion, localidad, departamen, categ
- **`machinedata`** (9,452 reg, 13 campos): fecha_hora, maq_gatway, maq_placa, maq_dhcp, maq_leasou, maq_leasin, maq_server, maq_domain, maq_user, maq_nombre, maq_ip, maq_subnet, maq_mac
- **`paramfer`** (6,944 reg, 9 campos): fecha, feriado, feriadon, sabado, domingo, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`controldtos`** (5,265 reg, 15 campos): cfile_env, fecha_envi, cperiodo, eregistros, nimporte, fecha_rece, erecibidos, nrecibidos, eaplicados, naplicados, erechazado, nrechazado, cfile_rec, usuario_en, usuario_re
- **`symdeperf`** (4,538 reg, 9 campos): sec_usuper, sec_codacc, sec_descac, sec_prompt, sec_nivela, sec_tipoac, sec_doacce, sec_keyacc, sec_condac
- **`perfiles`** (4,139 reg, 8 campos): perfil, sistema, agrupamien, posicion, tipo, descripcio, programas, habilitado
- **`organismos`** (3,709 reg, 11 campos): organo, nombre, domicilio, telefono, saf, debauto, orgaliq, capresca, nagrupa, nagrupa1, nombreagru
- **`tmpmaedio`** (1,131 reg, 22 campos): cidcliente, norgano, corgaorigi, no_agente, nclacar, ntdoc, ndoc, csexo, ccuil, capenom, cdomicilio, clocalidad, fnacim, fingre, cestciv, nhaberbrut, nsucbco, nctabco, ldebauto, lagjs, fecha_actu, cusuactu
- **`paramgral`** (664 reg, 19 campos): etabla, cdenominac, codigop, ecodigo, cdescripci, cdesred, cvalor, cvalor1, cvalor2, fvalor, fvalor1, fvalor2, evalor1, evalor2, evalor3, nvalor1, nvalor2, nvalor3, lvalor
- **`gectrldbf`** (483 reg, 2 campos): ffecha, lproceso
- **`usuarios`** (267 reg, 13 campos): nombre, usuario, sector, telefono, clave, perfil, no_cajero, fecult, lautoriza, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`maquinas`** (217 reg, 17 campos): codigo, maquina, descripcio, nro_serie, fecha_alta, estado, inventario, observacio, oficina_ac, operador, red, proveedor, facturadec, fecha_comp, baja, mot_baja, fec_baja
- **`bancosarg`** (179 reg, 2 campos): cod_banco, nom_banco
- **`oficinas`** (151 reg, 5 campos): id_oficina, denominaci, te_interno, te_linea, interna
- **`programas`** (128 reg, 6 campos): sistema, agrupamien, posicion, descripcio, programa, habilitado
- **`progmenu`** (127 reg, 7 campos): sistema, agrupamien, posicion, tipo, descripcio, programa, habilitado
- **`saf`** (92 reg, 2 campos): saf, descripcio
- **`apunca`** (57 reg, 7 campos): organo, cuil, ccuil, no_agente, apenom, sexoa, ndoc
- **`oficinas_m`** (47 reg, 6 campos): codigo, subgerenci, departamen, division, seccion, responsabl
- **`pararequisitos`** (47 reg, 3 campos): codigo, descripcio, tramite
- **`claves`** (38 reg, 4 campos): nro_cla, nombre, iniciales, cod_caj
- **`maeperfil`** (19 reg, 4 campos): cod_perfil, denominaci, habilitado, fecha_mod
- **`paramzona`** (14 reg, 3 campos): zona, descripcio, interior
- **`paramdoc`** (11 reg, 2 campos): tipo, descripcio
- **`parametro`** (9 reg, 5 campos): codigo, descripcio, valor1, valor2, valor3
- **`sistemas`** (9 reg, 3 campos): nosistema, denominaci, bit
- **`paramiva`** (6 reg, 5 campos): codigo, denominaci, denom_redu, alicuota, sobretasa
- **`maemonedas`** (5 reg, 3 campos): codigo, denominaci, tipo
- **`paramseg`** (5 reg, 9 campos): codigo, denominaci, importe, valor1, valor2, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`movimientos`** (4 reg, 8 campos): fecha, codigo, oficina, responsabl, motivo, temporal, operador, oficina_or
- **`mantenimiento`** (2 reg, 6 campos): fecha, codigo, motivo, reparado, fecha_repa, service
- **`proveedores`** (1 reg, 17 campos): nproveedor, cuit, crazonsoc, contacto, cdomicilio, clocalidad, cdepto, nprovincia, ctipoiva, niibb, lanulado, fanulado, uanulado, falta, calta, fmodi, cmodi

## Juegos — 40 tablas · 51,786 registros

- **`iejue20210809`** (2,589 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210803`** (2,545 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210810`** (2,525 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210818`** (2,403 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210820`** (2,305 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202107062`** (2,158 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210824`** (1,920 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210819`** (1,706 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210831`** (1,647 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210903`** (1,513 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202107261`** (1,501 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210813`** (1,481 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210827`** (1,446 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210806`** (1,395 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202108301`** (1,285 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202108231`** (1,281 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210730`** (1,163 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210728`** (1,131 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210830`** (1,131 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210729`** (1,130 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202107121`** (1,125 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210906`** (1,096 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210826`** (1,084 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202109061`** (1,084 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210817`** (1,077 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202108171`** (1,039 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210805`** (1,016 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202108021`** (1,012 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202107191`** (997 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210804`** (953 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210901`** (939 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210902`** (856 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210802`** (850 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202107061`** (820 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202108261`** (820 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210812`** (811 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210823`** (774 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue20210811`** (626 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`iejue202108091`** (498 reg, 10 campos): n_agen, c_juego, d_juego, n_sorteo, c_codigo, d_codigo, d_operac, importe, c_moneda, c_resumen
- **`age_cbu`** (54 reg, 3 campos): no_agencia, no_subage, cbu

## Mesa — 3 tablas · 510,316 registros

- **`pases`** (428,060 reg, 12 campos): id_tramite, id_letra, id_nro, id_ano, i_d, fecha_pase, oficina_or, texto, oficina_de, activo, falta, calta
- **`tramites`** (82,225 reg, 26 campos): id_tramite, id_letra, id_nro, id_ano, i_d, rep_origen, id_orig_le, id_orig_nr, id_orig_an, jubilado, id_tipo_as, id_nro_ase, nombre_ase, referencia, id_tipo_in, id_nro_ini, nombre_ini, iniciador, destino, estado, oficina_ac, cfile
- **`tipotram`** (31 reg, 3 campos): tipo, descripcio, des_red

## Seguros — 31 tablas · 20,192,017 registros

- **`liqsegur`** (10,123,264 reg, 18 campos): nro_agente, cuil, apeynom, actividad, bandera, remuimpo, d_svco, d_ss, d_sc, d_svca, ubicacion, saf, codorigen, claseycar, codigo, periodo, declara, reemplaza
- **`liqsegur_menores_2014`** (9,144,315 reg, 18 campos): nro_agente, cuil, apeynom, actividad, bandera, remuimpo, d_svco, d_ss, d_sc, d_svca, ubicacion, saf, codorigen, claseycar, codigo, periodo, declara, reemplaza
- **`seguros`** (215,964 reg, 13 campos): codigo, no_poliza, fecha, cuil, no_agente, sexo, estado, baja, cantidad, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`ccseguros`** (180,501 reg, 10 campos): cuil, no_agente, sexo, periodo, seguro, importe, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`benefici`** (123,632 reg, 14 campos): tipo_agen, cuil_docu, seguro, documento, domicilio, nombre, vinculo, fichanro, codigo, fichero, cajon, grupo, otorgadapo, fecha_naci
- **`titulares`** (123,067 reg, 20 campos): cuil, tipo_titul, organo, apenom, tipo_doc, no_doc, sexo, no_agente, fecha_naci, domicilio, cantidad, fecha_alta, usuario_al, fecha_modi, usuario_mo, beneficiar, provincia, localidad, fecha_reep, beneficio
- **`liquid_dat`** (59,783 reg, 33 campos): id_ld, id_nro, id_letra, id_ano, i_d, id_nro_ase, seguro, capital, cobra, caracter_d, porcentage, siniestro, anio_sin, fojas, fecha_liq, nota, domicilio, fecha_fall, monto, encond_de, tipo_seg, mont_cuota
- **`aux_act`** (53,090 reg, 13 campos): estado, periodo, peso_bono, jurisdicc, repartici, dependenc, agente, cuil, nombre, s_vida, s_sepelio, s_conyuge, s_adicion
- **`requisitos`** (52,418 reg, 7 campos): cuildni, seguro, requisito, fecha_sol, fecha_pres, cumplido, fojas
- **`activos`** (33,647 reg, 18 campos): jurisdicci, reparticio, dependenci, agente, cuil, nombre, s_vida, s_sepelio, s_conyuge, s_adicion, s_subsidio, estado, p_vida, p_sepelio, p_conyuge, p_adiciona, p_subsidio, fecha_alta
- **`segurosap`** (32,356 reg, 8 campos): periodo, cuil, titular, remuneraci, seg_obliga, seg_sepeli, seg_conyug, seg_adicio
- **`jubilado`** (25,003 reg, 19 campos): tipo_benef, nro_benef, anses, nombre, nro_doc, tipo_doc, s_sepelio, s_obligat, estado, pagado_s, pagado_o, ult_actual, operador, fecha_nac, fecha_afi, domicilio, provincia, fec_reemp, departamen
- **`familia`** (9,012 reg, 7 campos): tipo_agen, cuil_docu, parentezco, documento, fecha_nac, nombre, discapacit
- **`acseguros`** (4,837 reg, 7 campos): source, data, count, weight, created, updated, user
- **`seg_pag`** (2,715 reg, 16 campos): ctipo, idseguro, cdesc, nro_res, fec_res, no_op, fecha_op, apenom, cuil, importe, retencione, total, fecha_alta, fechapago, pagado, _nullflags
- **`liquid_datbak`** (2,175 reg, 30 campos): id_nro, id_letra, id_ano, id_nro_ase, seguro, capital, cobra, caracter_d, porcentage, siniestro, anio_sin, fojas, fecha_liq, nota, domicilio, fecha_fall, monto, encond_de, tipo_seg, mont_cuota, cant_cuota, tipo_id_co
- **`movimien`** (1,881 reg, 9 campos): jurisdicc, repartici, dependenc, periodo, s_vida, s_sepelio, s_conyuge, s_adicion, s_obligat
- **`hsubsidio`** (1,656 reg, 9 campos): siniestro, benefici, dni, cuota, mon_cuo, fecha_pri, fecha_ulti, observa, subindice
- **`dependen`** (1,507 reg, 6 campos): jurisdicci, reparticio, dependenci, nombre, domicilio, telefono
- **`subsidio`** (885 reg, 13 campos): siniestro, benefici, dni, cuota, mon_cuo, fecha_pri, fecha_ulti, observa, subindice, mes, ano, suspendida, fecha_susp
- **`excombate`** (185 reg, 42 campos): nombre, cuil, dni, fecha_nac, obrasocial, observacio, nocuota, domicilio, localidad, dpto, cod_post, telefono, lug_nacim, est_civil, formulario, derecho_ha, conyge, padre_madr, hijos, rep_legal, dh_nombre, dh_dni
- **`codorgagap`** (100 reg, 5 campos): codigo, declarado, denomina, activo, municipio
- **`operador`** (11 reg, 6 campos): numero, nombre, telefono, domicilio, clave, ult_camb
- **`regpago`** (5 reg, 11 campos): no_doc, legajo, mes, anio, recibo_no, fec_pago, svao, svo, ss, svac, observacio
- **`paraseguros`** (4 reg, 12 campos): id_tabla, tabla, codigo, descripcio, valor1, valor2, valor3, valor4, fecha_alta, usuario_al, fecha_modi, usuario_mo
- **`baja`** (2 reg, 2 campos): tipo, baja
- **`l5182titular`** (1 reg, 16 campos): ccuil, capenom, ntipodoc, nnrodoc, cdomicilio, clocalidad, cdepto, ccodpos, ctelefonos, ffecnac, clugarnac, nestciv, falta, cusualta, fmodi, cusumod
- **`l5182benef`** (1 reg, 19 campos): ccuiltit, ccuilbene, capenom, ntipdoc, nnrodoc, ntiparen, cdomicilio, clocalidad, cdepto, ccodpos, ctelefono, ffecnac, clugarnac, nestciv, nporcent, falta, cusualta, fmodi, cusumodi
- **`l5182liquida`** (0 reg, 21 campos): ccuiltitul, ccuilbene, ffecha, nbasecat10, nporcentaj, nresolucio, ffecreso, nop, ffecop, nliquida, ffecliq, mdetalle, ndescuento, ndescuent2, ndescuent3, lpagado, fechapago, falta, cusualta, fmodi, cusumodi
- **`aux_jub`** (0 reg, 11 campos): provincia, departamen, banco, tipo_benef, nro_benef, nombre, domicilio, nro_doc, tipo_doc, s_sepelio, s_obligat
- **`pag_seg`** (0 reg, 6 campos): tipo_agent, cuil, fecha, seguro, expediente, importe
