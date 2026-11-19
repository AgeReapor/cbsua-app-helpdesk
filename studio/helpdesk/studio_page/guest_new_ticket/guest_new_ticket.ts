import { useSettingsModal } from '@app/stores/settings'

export default function setup(context) {
  return {
    ...useSettingsModal(context),
  }
}
