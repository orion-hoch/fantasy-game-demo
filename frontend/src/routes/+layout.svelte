<script lang="ts">
  import '../app.css';

  let { children } = $props();
</script>

<div id="app">
  <header>
    <div class="header-inner">
      <h1>Sports Trivia and Games <span class="byline">by Orion Hoch</span></h1>
    </div>
  </header>

  {@render children()}
</div>

<style>
  .byline {
    font-size: 0.55em;
    font-weight: 400;
    opacity: 0.75;
    letter-spacing: 2px;
  }
</style>
