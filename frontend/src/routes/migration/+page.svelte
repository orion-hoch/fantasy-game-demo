<script lang="ts">
  import type { MigrationPageData } from '$lib/api/migration';

  let { data }: { data: MigrationPageData } = $props();
</script>

<section class="panel">
  <h2>Migration Surface Ledger</h2>
  <p class="small">Strategy: <strong>{data.strategy}</strong> · Source: <strong>{data.source}</strong></p>
  <div class="surface-grid">
    {#each data.surfaces as surface}
      <article class="surface-card">
        <h3>{surface.name}</h3>
        <p class="small">Legacy: <code>{surface.legacyRoute}</code></p>
        <p class="small">Target: <code>{surface.targetRoute}</code></p>
        <p>{surface.notes}</p>
        <div class="surface-meta">
          <span class={`status ${surface.status}`}>{surface.status}</span>
          <span class="chip">{surface.sport}</span>
          <a class="chip" href={surface.targetRoute}>Open target</a>
        </div>
      </article>
    {/each}
  </div>
</section>
