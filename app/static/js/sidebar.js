document.addEventListener("DOMContentLoaded", function() {
  const sidebar = document.querySelector(".sidebar");
  const sidebarBtn = document.querySelector(".bx-chevrons-right");
  const homeSection = document.querySelector(".home-section");
  const navLinks = document.querySelectorAll(".nav-links li");

  // Apply no-transition class to disable animations
  sidebar.classList.add('no-transition');
  homeSection.classList.add('no-transition');
  navLinks.forEach(li => li.classList.add('no-transition'));

  // Check sessionStorage to set the initial state of the sidebar
  if (sessionStorage.getItem('sidebarOpen') === 'false') {
      sidebar.classList.add("close");
      sidebarBtn.classList.replace("bx-chevrons-left", "bx-chevrons-right");
  } else {
      sidebar.classList.remove("close");
      sidebarBtn.classList.replace("bx-chevrons-right", "bx-chevrons-left");
  }

  // Allow for CSS transitions after initial state is set
  setTimeout(() => {
      sidebar.classList.remove('no-transition');
      homeSection.classList.remove('no-transition');
      navLinks.forEach(li => li.classList.remove('no-transition'));
  }, 0);  // Delay removal of no-transition until after paint

  // Toggle sidebar and store state in sessionStorage
  sidebarBtn.addEventListener("click", () => {
      sidebar.classList.toggle("close");
      if (sidebar.classList.contains("close")) {
          sidebarBtn.classList.replace("bx-chevrons-left", "bx-chevrons-right");
          sessionStorage.setItem('sidebarOpen', 'false');
      } else {
          sidebarBtn.classList.replace("bx-chevrons-right", "bx-chevrons-left");
          sessionStorage.setItem('sidebarOpen', 'true');
      }
  });
});
