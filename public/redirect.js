(() => {
  const target = new URL("https://realtysystemsfoundry.onrender.com/app/");
  target.search = window.location.search;
  target.hash = window.location.hash;
  window.location.replace(target.toString());
})();
