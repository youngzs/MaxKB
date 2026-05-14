import { t } from '@/locales'

export const themeList = [
  {
    label: t('theme.default'),
    value: '#3370FF',
    loginBackground: 'default',
  },
  {
    label: t('theme.orange'),
    value: '#FF8800',
    loginBackground: 'orange',
  },
  {
    label: t('theme.green'),
    value: '#00B69D',
    loginBackground: 'green',
  },
  {
    label: t('theme.purple'),
    value: '#7F3BF5',
    loginBackground: 'purple',
  },
  {
    label: t('theme.red'),
    value: '#F01D94',
    loginBackground: 'red',
  },
]

export function getThemeImg(val: string) {
  if (!val) return 'default'
  return themeList.filter((v) => v.value === val)?.[0]?.loginBackground || 'default'
}

export const defaultSetting = {
  icon: '',
  loginLogo: '',
  loginImage: '',
  title: 'MaxKB',
  slogan: t('theme.defaultSlogan'),
}

export const defaultPlatformSetting = {
  // 默认隐藏「用户手册 / 论坛 / 项目」三个外链入口，避免私有部署引导用户去 MaxKB 官网。
  // 管理员可在「系统设置 → 外观设置」中重新勾选并填入自有品牌链接。
  showUserManual: false,
  userManualUrl: t('layout.userManualUrl'),
  showForum: false,
  forumUrl: t('layout.forumUrl'),
  showProject: false,
  projectUrl: '',
}

export function hexToRgba(hex?: string, alpha?: number) {
  // 将16进制颜色值的两个字符一起转换成十进制
  if (!hex) {
    return ''
  } else {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)

    // 返回RGBA格式的字符串
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
  }
}
