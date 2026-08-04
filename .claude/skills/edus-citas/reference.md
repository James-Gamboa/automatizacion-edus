# EDUS DOM / Guide Reference

Official guide: https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss/blob/main/EDUS-Citas-Automation-Guide.md

## DOM IDs

| Element | ID |
|---------|-----|
| Form login | `formInicioSesion` |
| Tipo identificación | `formInicioSesion:tipIdentificacion_input` |
| Usuario | `formInicioSesion:usuario` |
| Clave | `formInicioSesion:clave` |
| CAPTCHA input | `formInicioSesion:captchaDigitado` |
| Botón login | `formInicioSesion:ejecutarPaso1` |
| Form principal | `formSIAC` |
| Botón agregar cita | `formSIAC:btnMenuAdd` |
| Select servicio | `formSIAC:menuServicios_input` |
| Select especialidad | `formSIAC:menuEspecialidades_input` |
| Tabla cupos | `formSIAC:cuposDisponibles` |
| Tabla familiares | `formSIAC:tablaFamiliares` |
| Tabla citas familiar | `formSIAC:tablaCitasFam` |

## Specialty codes

| Specialty | Servicio | Especialidad |
|-----------|----------|--------------|
| Medicina General | `1` | `1033` |
| Odontología | resolve by label `ODONTO*` (optional `ODONTO_SERVICIO` / `ODONTO_ESPECIALIDAD`) |

## Env vars

See project `.env.example`.
