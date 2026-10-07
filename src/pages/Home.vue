<script setup>
import { computed, onMounted, ref } from "vue";
import {
  ArrowRight,
  ArrowUpRight,
  Gamepad2,
  BookOpen,
  Wrench,
  Sparkles,
  MessageCircle,
} from "@lucide/vue";
import { api, site, dateLabel } from "../api";
import ContentCard from "../components/ContentCard.vue";
import HomeCarousel from "../components/HomeCarousel.vue";

const items = ref([]),
  comments = ref([]),
  error = ref("");
const sections = [
  {
    type: "game",
    title: "玩点有趣的",
    english: "PLAY & EXPLORE",
    path: "/games",
    icon: Gamepad2,
    description: "小小的游戏，大大的想象力。",
  },
  {
    type: "knowledge",
    title: "知识慢慢积累",
    english: "LEARN & GROW",
    path: "/knowledge",
    icon: BookOpen,
    description: "把学到的、想到的，认真记下来。",
  },
  {
    type: "tool",
    title: "好工具，值得分享",
    english: "TOOLS & RESOURCES",
    path: "/tools",
    icon: Wrench,
    description: "让创作更顺手，让日常更轻松。",
  },
];
const filtered = (type) =>
  items.value
    .filter((item) =>
      type === "knowledge"
        ? ["article", "note"].includes(item.type)
        : item.type === type
    )
    .slice(0, 2);
const visibleSections = computed(() =>
  sections.filter((section) => filtered(section.type).length)
);
const firstSection = computed(() => visibleSections.value[0]);
const hasFeaturedGame = computed(() =>
  visibleSections.value.some((section) => section.type === "game")
);
onMounted(async () => {
  try {
    const [games, knowledge, tools, board] = await Promise.all([
      api("/contents?featured=1&type=game"),
      api("/contents?featured=1&type=knowledge"),
      api("/contents?featured=1&type=tool"),
      api("/comments"),
    ]);
    items.value = [...games.items, ...knowledge.items, ...tools.items];
    comments.value = board.items.slice(0, 3);
  } catch (e) {
    error.value = e.message;
  }
});
</script>

<template>
  <div
    class="home-layout"
    :class="{
      'intro-first': site.settings.home_intro_first !== false,
      'has-carousel': !!site.settings.carousel?.length,
      'compact-home': visibleSections.length === 1,
      'no-featured': visibleSections.length === 0,
    }"
  >
    <HomeCarousel
      v-if="site.settings.carousel?.length"
      :slides="site.settings.carousel"
    />
    <section class="hero">
      <div class="hero-copy">
        <div v-if="site.settings.hero_kicker" class="eyebrow">
          <span class="live-dot"></span> {{ site.settings.hero_kicker }}
        </div>
        <h1 v-if="site.settings.hero_title">{{ site.settings.hero_title }}</h1>
        <p v-if="site.settings.tagline">{{ site.settings.tagline }}</p>
        <div class="hero-buttons">
          <RouterLink v-if="firstSection" :to="firstSection.path" class="button"
            >{{
              {
                game: "探索我的创作",
                knowledge: "看看知识笔记",
                tool: "发现好工具",
              }[firstSection.type]
            }}
            <ArrowRight :size="17" /></RouterLink
          ><RouterLink to="/board" class="hero-secondary"
            >打个招呼 <MessageCircle :size="17"
          /></RouterLink>
        </div>
        <div v-if="site.settings.hero_note" class="hero-footnote">
          <span></span> {{ site.settings.hero_note }}
        </div>
      </div>
      <div class="hero-art" aria-hidden="true">
        <div class="art-grid"></div>
        <span class="art-label">IDEAS IN PROGRESS</span>
        <div class="art-orbit orbit-one"></div>
        <div class="art-orbit orbit-two"></div>
        <div v-if="hasFeaturedGame" class="floating-card art-game">
          <Gamepad2 :size="44" /><span>LET'S PLAY</span><i>✦</i>
        </div>
        <div class="floating-card art-code">
          <span class="code-dots">● ● ●</span><b>&lt;hello world /&gt;</b
          ><span class="code-line"></span><span class="code-line short"></span>
        </div>
        <div class="floating-card art-note">
          <Sparkles :size="23" /><b>Stay curious.</b><span>让好奇心带路</span>
        </div>
        <span class="art-spark spark-one"></span
        ><span class="art-spark spark-two">+</span
        ><span class="art-coordinate">CREATE / LEARN / REPEAT</span>
      </div>
    </section>
    <div class="home-feed">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <section
        v-for="section in visibleSections"
        :key="section.type"
        :class="['home-section', 'section-' + section.type]"
      >
        <div class="section-heading">
          <div>
            <div class="section-kicker">{{ section.english }}</div>
            <h2>
              <component :is="section.icon" :size="21" />{{ section.title }}
            </h2>
            <p>{{ section.description }}</p>
          </div>
          <RouterLink :to="section.path"
            >查看全部 <ArrowRight :size="15"
          /></RouterLink>
        </div>
        <div class="card-grid">
          <ContentCard
            v-for="item in filtered(section.type)"
            :key="item.id"
            :item="item"
          />
        </div>
      </section>
    </div>
    <section class="about-card home-about">
      <div class="about-top">
        <img
          v-if="site.settings.avatar"
          :src="site.settings.avatar"
          alt="站长头像"
        /><span v-else class="profile-avatar">柿<span>✦</span></span
        ><span class="small-label">ABOUT ME</span>
      </div>
      <h2>
        欢迎来到<br />{{ site.settings.name }} <span class="wave"></span>
      </h2>
      <span v-if="site.settings.placeholder" class="placeholder-badge"
        >个人资料占位 · 待站长完善</span
      >
      <p v-if="site.settings.bio">{{ site.settings.bio }}</p>
      <div class="about-links">
        <a
          v-for="link in site.settings.links"
          :key="link.url"
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          >{{ link.label }}<ArrowUpRight :size="14" /></a
        ><RouterLink to="/board"
          >给我留言 <ArrowUpRight :size="15"
        /></RouterLink>
      </div>
    </section>
    <section class="sidebar-note home-note">
      <span></span>
      <p>不急着抵达，<br />享受创造的过程。</p>
      <small>MAKE SOMETHING YOU LOVE</small>
    </section>
    <section class="recent-comments home-recent">
      <h3><MessageCircle :size="17" />最近的声音</h3>
      <div v-if="!comments.length" class="muted small">
        还没有留言。<br />欢迎成为第一个打招呼的人。
      </div>
      <RouterLink
        v-for="item in comments"
        :key="item.id"
        to="/board"
        class="recent-comment"
        ><strong>{{ item.nickname }}</strong>
        <p>{{ item.body }}</p>
        <time>{{ dateLabel(item.created_at) }}</time></RouterLink
      ><RouterLink class="text-link" to="/board">去留言板坐坐 →</RouterLink>
    </section>
  </div>
</template>
