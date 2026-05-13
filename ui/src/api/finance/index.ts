/**
 * Finance API — barrel export.
 * Gate 2 Track B: project CRUD.
 * Gate 3 Track C: template library + generation history.
 * Gate 4 Track C: materials task workspace.
 */
export * from './type'
export * from './project'
export * from './template'
export * from './generation'
export * from './materials-task'
export { default as financeProjectApi } from './project'
export { default as financeTemplateApi } from './template'
export { default as financeGenerationApi } from './generation'
export { default as financeMaterialsTaskApi } from './materials-task'
