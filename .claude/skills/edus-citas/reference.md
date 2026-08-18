# EDUS DOM / Guide Reference

Official guide (local): [EDUS-Citas-Automation-Guide.md](../../../EDUS-Citas-Automation-Guide.md)

## Solicitar Cita (UI order)

1. **Establecimiento de Salud** — assigned (read-only), e.g. `227404 - EBAIS MILPA 1`
2. **Servicio \*** — dropdown options typically:
   - `MEDICINA`
   - `ODONTOLOGIA`
3. **Especialidad \*** — starts as `SELECCIONE ESPECIALIDAD...` until Servicio is chosen
4. Cupos table — Fecha, Hora de Cita, N° de Cita, Consultorio, Funcionario, Ver cita

**Must select Servicio first** (open PrimeFaces menu + click). Hidden `_input` alone leaves the visible label empty and Especialidad stuck on the placeholder.

## DOM IDs

| Element                             | ID                                  |
| ----------------------------------- | ----------------------------------- |
| Form login                          | `formInicioSesion`                  |
| Usuario                             | `formInicioSesion:usuario`          |
| Clave                               | `formInicioSesion:clave`            |
| CAPTCHA input                       | `formInicioSesion:captchaDigitado`  |
| Botón login                         | `formInicioSesion:ejecutarPaso1`    |
| Form principal                      | `formSIAC`                          |
| Botón agregar cita                  | `formSIAC:btnMenuAdd`               |
| Select servicio (hidden input)      | `formSIAC:menuServicios_input`      |
| Select servicio (visible label)     | `formSIAC:menuServicios_label`      |
| Select especialidad (hidden input)  | `formSIAC:menuEspecialidades_input` |
| Select especialidad (visible label) | `formSIAC:menuEspecialidades_label` |
| Tabla cupos                         | `formSIAC:cuposDisponibles`         |
| Tabla familiares                    | `formSIAC:tablaFamiliares`          |

## Specialty presets

| Intent           | Servicio (UI) | Especialidad (UI)             | Codes                             |
| ---------------- | ------------- | ----------------------------- | --------------------------------- |
| Medicina general | MEDICINA      | MEDICINA GENERAL              | servicio `1`, especialidad `1033` |
| Odontología      | ODONTOLOGIA   | ODONTOLOGIA GENERAL (typical) | by label / env override           |

## Env vars

See project `.env.example`.
