document.addEventListener('DOMContentLoaded', function () {
  const track = document.querySelector('.carousel-track');
  
  // FIX: Exit function if the carousel track doesn't exist on this page
  if (!track) {
    return;
  }

  const slides = Array.from(track.children);
  
  // FIX: Safety check to prevent errors if track exists but is empty
  if (slides.length === 0) {
    return;
  }

  const slideWidth = slides[0].getBoundingClientRect().width;

  // Clone slides for infinite loop
  const clones = slides.map(slide => {
    const clone = slide.cloneNode(true);
    clone.classList.add('clone');
    return clone;
  });
  track.append(...clones);

  let currentIndex = 0;

  function updateCarousel() {
    track.style.transform = `translateX(-${currentIndex * slideWidth}px)`;

    if (currentIndex >= slides.length) {
      // Jump back to the beginning without animation
      setTimeout(() => {
        track.style.transition = 'none';
        currentIndex = 0;
        track.style.transform = `translateX(0)`;
        setTimeout(() => {
          track.style.transition = 'transform 0.5s ease-in-out';
        });
      }, 500);
    }
  }

  setInterval(() => {
    currentIndex++;
    updateCarousel();
  }, 3000);
});