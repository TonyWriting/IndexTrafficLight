<script setup lang="ts">
import { onHide, onLaunch, onShow } from '@dcloudio/uni-app'
import { startPremiumAutoRefresh, stopPremiumAutoRefresh } from './api'

onLaunch(() => {
  startPremiumAutoRefresh()
})

onShow(() => {
  startPremiumAutoRefresh()
})

onHide(() => {
  stopPremiumAutoRefresh()
})
</script>
<style>
/* Make H5 text selectable for copying while keeping controls and charts usable. */
page,
view,
text {
  -webkit-user-select: text;
  user-select: text;
}

canvas,
.refresh-btn,
.state-action,
.range-tab,
.status-badge,
.open-text,
.tip-close {
  -webkit-user-select: none;
  user-select: none;
}
</style>
