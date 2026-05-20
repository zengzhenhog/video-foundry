<script setup lang="ts">
import { computed } from "vue";

import type { VoicePreset, VoiceProviderInfo } from "../types/project";

interface VoiceConfigDraft {
  provider: string;
  voice_id: string;
  language: string;
  speed: number;
  volume_gain_db: number;
  style: string | null;
}

const props = defineProps<{
  providers: VoiceProviderInfo[];
  presets: VoicePreset[];
  disabled?: boolean;
}>();

const model = defineModel<VoiceConfigDraft>({ required: true });

const providerPresets = computed(() =>
  props.presets.filter((preset) => preset.provider === model.value.provider),
);

function applyPreset(event: Event): void {
  const presetId = (event.target as HTMLSelectElement).value;
  const preset = props.presets.find(
    (candidate) => candidate.provider === model.value.provider && candidate.id === presetId,
  );
  if (!preset) {
    return;
  }
  model.value.voice_id = preset.id;
  model.value.language = preset.language;
  model.value.style = preset.style;
}

function normalizeStyle(event: Event): void {
  const value = (event.target as HTMLInputElement).value.trim();
  model.value.style = value || null;
}
</script>

<template>
  <section class="panel voice-config">
    <div class="panel__header">
      <div>
        <p class="eyebrow">旁白设置</p>
        <h2>音色配置</h2>
      </div>
    </div>

    <div class="form-grid">
      <label>
        <span>Provider</span>
        <select v-model="model.provider" :disabled="disabled">
          <option v-for="provider in providers" :key="provider.id" :value="provider.id">
            {{ provider.name }}
          </option>
        </select>
      </label>

      <label>
        <span>预设音色</span>
        <select :value="model.voice_id" :disabled="disabled" @change="applyPreset">
          <option v-for="preset in providerPresets" :key="preset.id" :value="preset.id">
            {{ preset.name }}
          </option>
        </select>
      </label>

      <label>
        <span>Voice ID</span>
        <input v-model="model.voice_id" type="text" maxlength="120" :disabled="disabled" />
      </label>

      <label>
        <span>语言</span>
        <input v-model="model.language" type="text" maxlength="32" :disabled="disabled" />
      </label>

      <label>
        <span>语速</span>
        <input
          v-model.number="model.speed"
          type="number"
          min="0.5"
          max="2"
          step="0.05"
          :disabled="disabled"
        />
      </label>

      <label>
        <span>音量增益 dB</span>
        <input
          v-model.number="model.volume_gain_db"
          type="number"
          min="-24"
          max="12"
          step="0.5"
          :disabled="disabled"
        />
      </label>

      <label class="form-grid__wide">
        <span>风格</span>
        <input
          :value="model.style ?? ''"
          type="text"
          maxlength="80"
          :disabled="disabled"
          @input="normalizeStyle"
        />
      </label>
    </div>
  </section>
</template>
