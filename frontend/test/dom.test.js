/** @type { Router } */
let router;

beforeAll(async () => {
    await import('../src/main');
    router = globalThis.__routify.routers[0];
    await router.ready();
});

afterAll(async () => {
  console.log("Completed all tests xxxx");
});

afterEach(async () => {
  console.log("One test completed");
});

test('can see frontpage', async () => {
    expect(document.body.innerHTML).toContain('Main public page');
})

test('can see /hello-world', async () => {
    await router.url.push('/hello-world');
    expect(document.body.innerHTML).toContain('Hello world!');
})
