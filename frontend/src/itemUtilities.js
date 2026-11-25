export function validGenerationOptions(options) {
  return options && ['numeric', 'alphanumeric'].includes(options.character_type) &&
    Number.isInteger(options.length) && options.length >= (options.character_type === 'numeric' ? 1 : 2) &&
    options.length <= 140
}

const generationKey = (profile, target) => `esafepos-code-generator:${profile}:${target}`

export function loadGenerationOptions(profile, target) {
  try {
    const options = JSON.parse(localStorage.getItem(generationKey(profile, target)))
    if (validGenerationOptions(options)) return { character_type: options.character_type, length: options.length }
  } catch { /* Browser storage may be unavailable. */ }
  return { character_type: 'numeric', length: 5 }
}

export function saveGenerationOptions(profile, target, options) {
  if (!validGenerationOptions(options)) return
  try {
    localStorage.setItem(generationKey(profile, target), JSON.stringify(options))
  } catch { /* Generation still works without saved preferences. */ }
}
