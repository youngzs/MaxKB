import { defineStore } from 'pinia'
import { cloneDeep } from 'lodash'
import { useElementPlusTheme } from 'use-element-plus-theme'
import ThemeApi from '@/api/system-settings/theme'
import type {Ref} from "vue";
export interface themeStateTypes {
  themeInfo: any
}
const defalueColor = '#3370FF'

const useThemeStore = defineStore('theme', {
  state: (): themeStateTypes => ({
    themeInfo: null,
  }),
  actions: {
    isDefaultTheme() {
      return !this.themeInfo?.theme || this.themeInfo?.theme === defalueColor
    },

    setTheme(data?: any) {
      const { changeTheme } = useElementPlusTheme(this.themeInfo?.theme || defalueColor)
      changeTheme(data?.['theme'] || defalueColor)
      this.themeInfo = cloneDeep(data)
      // 同步浏览器标签页 title。复用 themeForm.title（"网站名称"字段）——
      // 该字段在 /admin/system/setting/theme 已可编辑，无需再加 UI。
      // 留空 / null / 全空白都退回 'MaxKB'，避免空 title 让浏览器显示 URL。
      const customTitle = (data?.title || '').trim()
      document.title = customTitle || 'MaxKB'
    },

    async theme(loading?: Ref<boolean>) {
      return await ThemeApi.getThemeInfo(loading).then((ok) => {
        this.setTheme(ok.data)
      })
    },
  },
})

export default useThemeStore
