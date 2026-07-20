<template>
  <section v-if="available" class="feedback-panel">
    <div v-if="submitted" class="feedback-thanks">
      <span aria-hidden="true">✓</span>
      <div>
        <strong>收到，谢谢你。</strong>
        <p>这条反馈只包含你的选择和主动填写的文字。</p>
      </div>
    </div>

    <template v-else>
      <div class="feedback-head">
        <div>
          <span>测试反馈</span>
          <h3>这份报告对你有帮助吗？</h3>
          <p>点一下就可以，不需要回小红书留言。</p>
        </div>
        <div class="rating-actions" role="group" aria-label="报告是否有帮助">
          <button type="button" :class="{ active: rating === 'helpful' }" @click="selectRating('helpful')">
            <span aria-hidden="true">✓</span>有帮助
          </button>
          <button type="button" :class="{ active: rating === 'not_helpful' }" @click="selectRating('not_helpful')">
            <span aria-hidden="true">×</span>不太有用
          </button>
        </div>
      </div>

      <div v-if="rating" class="feedback-detail">
        <div class="feedback-field">
          <label>你接下来会继续分析其他博主吗？</label>
          <div class="choice-row">
            <button
              v-for="choice in reuseChoices"
              :key="choice.value"
              type="button"
              :class="{ active: reuseIntent === choice.value }"
              @click="reuseIntent = choice.value"
            >
              {{ choice.label }}
            </button>
          </div>
        </div>

        <div class="feedback-field">
          <label>{{ rating === 'helpful' ? '最好用的是哪里？（可不填）' : '主要卡在哪里？（可不填）' }}</label>
          <div class="choice-row">
            <button
              v-for="choice in reasonChoices"
              :key="choice.value"
              type="button"
              :class="{ active: reason === choice.value }"
              @click="reason = choice.value"
            >
              {{ choice.label }}
            </button>
          </div>
        </div>

        <div class="feedback-field">
          <label for="feedback-comment">还想告诉我们什么？（最多 500 字）</label>
          <textarea id="feedback-comment" v-model="comment" maxlength="500" rows="3" placeholder="例如：哪句话看不懂，或者最希望增加什么。"></textarea>
        </div>

        <div class="submit-row">
          <span>不会上传 Cookie、账号链接或报告内容。</span>
          <button class="btn btn-primary" type="button" :disabled="submitting" @click="submit">
            {{ submitting ? '发送中...' : '发送反馈' }}
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { telemetryAPI } from '../api/client'

const props = defineProps<{ taskId: number }>()

const available = ref(false)
const rating = ref<'helpful' | 'not_helpful' | ''>('')
const reuseIntent = ref('')
const reason = ref('')
const comment = ref('')
const submitting = ref(false)
const submitted = ref(false)

const reuseChoices = [
  { label: '会', value: 'yes' },
  { label: '可能会', value: 'maybe' },
  { label: '不会', value: 'no' },
]

const positiveReasons = [
  { label: '结论清楚', value: 'clear_conclusion' },
  { label: '证据可信', value: 'useful_evidence' },
  { label: '行动建议', value: 'actionable' },
]

const negativeReasons = [
  { label: '结论不准', value: 'inaccurate' },
  { label: '不够好懂', value: 'hard_to_understand' },
  { label: '建议不实用', value: 'not_actionable' },
  { label: '数据有问题', value: 'data_issue' },
]

const reasonChoices = computed(() => rating.value === 'helpful' ? positiveReasons : negativeReasons)

function selectRating(value: 'helpful' | 'not_helpful') {
  if (rating.value !== value) reason.value = ''
  rating.value = value
}

async function submit() {
  if (!rating.value) return
  submitting.value = true
  try {
    const res = await telemetryAPI.feedback({
      task_id: props.taskId,
      feedback_kind: 'report',
      rating: rating.value,
      reason: reason.value,
      comment: comment.value,
      reuse_intent: reuseIntent.value,
    })
    if (res.data.accepted) submitted.value = true
  } finally {
    submitting.value = false
  }
}

async function loadAvailability() {
  try {
    const res = await telemetryAPI.preferences()
    available.value = Boolean(res.data.available && res.data.consent === 'granted')
  } catch {
    available.value = false
  }
}

onMounted(() => {
  loadAvailability()
  window.addEventListener('telemetry-consent-changed', loadAvailability)
})

onUnmounted(() => {
  window.removeEventListener('telemetry-consent-changed', loadAvailability)
})
</script>

<style scoped>
.feedback-panel {
  border: 1px solid #e6c9d1;
  border-top: 5px solid #1ca96b;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(194, 35, 75, 0.07);
  padding: 22px;
}

.feedback-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.feedback-head > div:first-child > span {
  color: #118354;
  font-size: 12px;
  font-weight: 900;
}

.feedback-head h3 {
  margin: 3px 0;
  font-size: 21px;
}

.feedback-head p,
.submit-row span,
.feedback-thanks p {
  color: #746b70;
  font-size: 13px;
}

.rating-actions,
.choice-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rating-actions button,
.choice-row button {
  min-height: 36px;
  border: 1px solid #dfcbd0;
  border-radius: 6px;
  background: #fff;
  color: #51484d;
  cursor: pointer;
  font-weight: 800;
  padding: 7px 12px;
}

.rating-actions button.active,
.choice-row button.active {
  border-color: #ff3158;
  background: #fff0f3;
  color: #d9133f;
}

.feedback-detail {
  display: grid;
  gap: 16px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #f1e3e7;
}

.feedback-field label {
  margin-bottom: 7px;
  font-size: 13px;
}

.submit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.feedback-thanks {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 70px;
}

.feedback-thanks > span {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #dcf8e9;
  color: #087342;
  font-weight: 950;
}

@media (max-width: 680px) {
  .feedback-panel { padding: 16px; }
  .feedback-head,
  .submit-row {
    align-items: stretch;
    flex-direction: column;
  }
  .rating-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .rating-actions button,
  .submit-row .btn {
    justify-content: center;
  }
}
</style>
