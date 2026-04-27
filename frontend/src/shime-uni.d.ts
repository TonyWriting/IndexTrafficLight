export {}

declare global {
  const uni: any
}

declare module "vue" {
  interface ComponentCustomOptions {}
}
