<script lang="ts">
export default {}
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
.state-action,
.range-tab,
.status-badge,
.tip-close {
  -webkit-user-select: none;
  user-select: none;
}
</style>
