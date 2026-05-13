/**
 * Finance API — barrel export.
 * Gate 2 Track B: project CRUD.
 * Gate 3 Track C: template library + generation history.
 */
export * from './type'
export * from './project'
export * from './template'
export * from './generation'
export { default as financeProjectApi } from './project'
export { default as financeTemplateApi } from './template'
export { default as financeGenerationApi } from './generation'
