<script lang="ts">
    import {
        Card,
        CardHeader,
        CardBody,
        Form,
        FormGroup,
        Label,
        Input,
        Button,
        Icon
    } from "sveltestrap";
    import { signin } from "@/stores/user";
    import { _ } from "@/i18n";

    let username: string;
    let password: string;
    let isError: boolean;
    let showPassword: boolean = false;

    async function handleSubmit(event: Event) {
        event.preventDefault();
        isError = false;
        try {
            await signin(username, password);
        } catch (error) {
            isError = true;
        }
    }

    function togglePasswordVisibility() {
        showPassword = !showPassword;
    }
</script>

<Card class="w-25 mx-auto my-auto">
  <CardHeader>{$_("login_to_members")}</CardHeader>
  <CardBody>
    <Form on:submit={handleSubmit}>
      <FormGroup>
        <Label for="username">{$_("username")}</Label>
        <Input
                class={isError ? "border-danger" : ""}
                type="text"
                name="username"
                bind:value={username}
                required
        />
      </FormGroup>
      <FormGroup>
        <Label for="password">{$_("password")}</Label>
        <div class="input-group">
          <Input
                  class={isError ? "border-danger" : ""}
                  type={showPassword ? "text" : "password"}
                  name="password"
                  bind:value={password}
                  minlength={8}
                  maxlength={24}
                  required
          />
          <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <span class="input-group-text" onclick={togglePasswordVisibility} style="cursor: pointer;" aria-controls="password">
            {#if showPassword}
              <Icon name="eye-fill"  />
            {:else}
              <Icon name="eye-slash-fill"  />
            {/if}
          </span>
        </div>
      </FormGroup>
      {#if isError}
        <p class="text-danger">Wrong credentials!</p>
      {/if}
      <div class="w-100 d-flex align-items-end">
        <Button type="submit" color="primary" class="ms-auto">{$_("login")}</Button>
      </div>
    </Form>
  </CardBody>
</Card>

<style>
    .input-group {
        display: flex;
        align-items: center;
    }
    .input-group-text {
        background: none;
        border: none;
    }
</style>