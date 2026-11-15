<template>
  <span class="product-art" :class="category">
    <img v-if="item.image && failed !== item.image" :src="item.image" alt="" @error="failed = item.image" />
    <component v-else :is="icons[category]" aria-hidden="true" />
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Apple, Beef, CookingPot, Milk, Package, Shirt, SprayCan, Wheat } from '@lucide/vue'

const props = defineProps({ item: { type: Object, required: true } })
const failed = ref('')
const icons = { produce: Apple, meat: Beef, kitchen: CookingPot, dairy: Milk, other: Package,
  clothing: Shirt, cleaning: SprayCan, grains: Wheat }
const categories = [
  ['kitchen', /\b(bowls?|spoons?|cookers?|cookware|kitchenware|plates?)\b/i],
  ['cleaning', /\b(detergent|cleaning|bleach|disinfectant)\b/i],
  ['dairy', /\b(milk|yog(?:h)?urts?|curd|cheese|dairy)\b/i],
  ['grains', /\b(rice|flour|grain|oats|wheat|cereal)\b/i],
  ['produce', /\b(fruits?|vegetables?|produce|apples?|bananas?|tomatoes?)\b/i],
  ['meat', /\b(meat|chicken|beef|fish|seafood)\b/i],
  ['clothing', /\b(clothing|apparel|shirts?|trousers)\b/i],
]
const category = computed(() => {
  for (const value of [props.item.name, props.item.group]) {
    const match = categories.find(([, pattern]) => pattern.test(value || ''))
    if (match) return match[0]
  }
  return 'other'
})
</script>

<style scoped>
.product-art { display: grid; place-items: center; width: var(--product-art-size, 48px); height: var(--product-art-size, 48px); flex: none; border-radius: 12px; background: #e7effb; color: #245393; overflow: hidden; }
.product-art svg { width: 52%; height: 52%; }
.product-art img { width: 100%; height: 100%; object-fit: contain; }
.produce { background: #e5f5df; color: #376038; }
.grains, .kitchen { background: #ffedd4; color: #80500d; }
.dairy { background: #e8efff; color: #2853a0; }
.meat { background: #fbe8e9; color: #853948; }
</style>
