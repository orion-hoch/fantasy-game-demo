<script lang="ts">
  let { data } = $props();
</script>

<section class="panel placeholder">
  <h2>{data.sport.toUpperCase()} {data.slug}</h2>
  <p>
    This is the target SvelteKit route for the migrated game surface. The Flask version remains live until
    this route reaches parity and is promoted in the strangler rollout.
  </p>
</section>
