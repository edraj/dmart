import { writable } from "svelte/store";

let localstorage_user;

if (localStorage.getItem("signedin_user"))
  localstorage_user = JSON.parse(localStorage.getItem("signedin_user"));

const signedin_user = writable(localstorage_user || false);

signedin_user.authenticate = function() {
  const account = JSON.parse(localStorage.getItem("signedin_user"));
  signedin_user.set(account);
}

signedin_user.login = function(account) {
  localStorage.setItem("signedin_user", JSON.stringify(account));
  signedin_user.set(account);
}

signedin_user.logout = function() {
  localStorage.removeItem('signedin_user')
  signedin_user.set(false);
}

export default signedin_user;
