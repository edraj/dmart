<script lang="ts">
    import { Col, Row, Input, Button } from "sveltestrap";
    import Chart from 'svelte-frappe-charts';
    import QueryFormStats from "@/components/management/QueryFormStats.svelte";

    let rows = $state([]);
    let plotType = $state("line");
    let x_axis = $state("");
    let y_axis = $state("");

    let bodyProps = $state([])
    function handleResponse(event: CustomEvent) {
        rows = event.detail.records;
        bodyProps = Object.keys(rows[0].attributes.payload.body);
    }

    let plotData = $state({
        labels: [],
        datasets: []
    });
    function handlePlotting() {
        plotData =  {
            labels: [],
            datasets: []
        }

        let labels = [];

        const y_keys = y_axis.split(",").map((key) => key.trim());
        const datasets = [];

        for (const row of $state.snapshot(rows)) {
            labels.push(row.attributes.payload.body[x_axis]);
        }

        y_keys.forEach((key) => {
            let values = [];
            for (const row of $state.snapshot(rows)) {
                values.push(row.attributes.payload.body[key]);
            }
            datasets.push({
                name: key,
                values: values,
            })
        });

        plotData = {
            labels: labels,
            datasets: datasets
        };
    }

</script>

<Col class="h-100 px-2 mt-2">
    <QueryFormStats on:response={handleResponse} />
    {#if rows.length}
        <Row class="my-3 mx-4">
            <Col sm="4">
                <Input
                        type="select"
                        bind:value={x_axis}
                >
                    {#each bodyProps as bodyProp}
                        <option value={bodyProp}>{bodyProp}</option>
                    {/each}
                </Input>
            </Col>
            <Col sm="4">
                <Input type="text" placeholder="Y-Axis" bind:value={y_axis} />
            </Col>
            <Col sm="4">
                <Input type="select" bind:value={plotType}>
                    <option value="line">Line</option>
                    <option value="bar">Bar</option>
                    <option value="pie">Pie</option>
                    <option value="percentage">Percentage</option>
                    <option value="heatmap">Heatmap</option>
                    <option value="donut">Donut</option>
                </Input>
            </Col>
        </Row>
        <Row class="mx-5">
            <Button on:click={handlePlotting}>Plot</Button>
        </Row>
        {#key plotData}
            <Chart data={plotData} type={plotType} isNavigable/>
        {/key}
    {/if}
</Col>
