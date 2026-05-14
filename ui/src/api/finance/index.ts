/**
 * Finance API — barrel export.
 * Gate 2 Track B: project CRUD.
 * Gate 3 Track C: template library + generation history.
 * Gate 4 Track C: materials task workspace.
 * Gate 5 Track B: SMTP send pipeline.
 * Gate 5 Track C: audit log admin page.
 */
export * from './type'
export * from './project'
export * from './template'
export * from './generation'
export * from './materials-task'
export * from './smtp-config'
export * from './email-template'
export * from './email-send'
export * from './audit-log'
export * from './document-sensitivity'
export { default as financeProjectApi } from './project'
export { default as financeTemplateApi } from './template'
export { default as financeGenerationApi } from './generation'
export { default as financeMaterialsTaskApi } from './materials-task'
export { default as financeSmtpConfigApi } from './smtp-config'
export { default as financeEmailTemplateApi } from './email-template'
export { default as financeEmailSendApi } from './email-send'
export { default as financeAuditLogApi } from './audit-log'
export { default as financeDocumentSensitivityApi } from './document-sensitivity'
