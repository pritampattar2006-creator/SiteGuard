// The one password every EMPLOYEE account uses (a demo value: it must be replaced before any real use). Supervisors have their own passwords.
export const EMPLOYEE_PASSWORD = process.env.DEFAULT_EMPLOYEE_PASSWORD || '123456789';
// The supervisors that exist now (the head supervisor and the sector supervisors) use the same password for this demo. Supervisors made later choose their own.
export const PRESENT_SUPERVISOR_PASSWORD = EMPLOYEE_PASSWORD;
