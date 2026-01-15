document.addEventListener("DOMContentLoaded", function () {
  const paymentForm = document.getElementById("payment-form");
  if (!paymentForm) {
    // This script is only for the checkout page.
    return;
  }

  const stripePublicKey = paymentForm.dataset.stripeKey;
  if (!stripePublicKey) {
    console.error("Stripe public key not found.");
    return;
  }

  const stripe = Stripe(stripePublicKey);
  const submitButton = document.getElementById("submit-button");
  const originalButtonText = submitButton.textContent;

  // --- 1. Initialize Stripe Elements ---
  let elements;
  let clientSecret;

  // Fetch Payment Intent and initialize elements
  initialize();

  // --- 2. Set up form submission ---
  paymentForm.addEventListener("submit", handleSubmit);

  // --- Functions ---

  // Fetches a payment intent and captures the client secret
  async function initialize() {
    const variantId = paymentForm.dataset.variantId;
    const quantity = paymentForm.dataset.quantity;

    try {
      const response = await fetch("/awakening/api/create-payment-intent/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_id: variantId, quantity: quantity }),
      });

      const data = await response.json();
      if (data.error) {
        showMessage(data.error);
        setLoading(true); // Disable form if PI creation fails
        return;
      }

      clientSecret = data.client_secret;

      // THEMED STRIPE ELEMENTS
      const appearance = {
        theme: "night",
        variables: {
          colorPrimary: "#22c55e", // Tailwind green-500
          colorBackground: "#052e16", // Dark green bg
          colorText: "#ffffff",
          colorDanger: "#ef4444",
          fontFamily: "monospace", // Terminal style
          spacingUnit: "4px",
          borderRadius: "2px",
        },
      };

      elements = stripe.elements({ clientSecret, appearance });

      const paymentElement = elements.create("card", {
        style: {
          base: {
            iconColor: "#22c55e",
            color: "#ffffff",
            fontFamily: "monospace",
            "::placeholder": {
              color: "#4ade80", // Lighter green placeholder
            },
          },
        },
      });
      paymentElement.mount("#card-element");
    } catch (error) {
      console.error("Error initializing payment:", error);
      showMessage("Could not connect to payment server.");
    }
  }

  // Handles the form submission
  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);

    const email = document.getElementById("email").value;

    const { error } = await stripe.confirmCardPayment(clientSecret, {
      payment_method: {
        card: elements.getElement("card"),
        billing_details: {
          name: document.getElementById("name").value,
          email: email,
          address: {
            line1: document.getElementById("address").value,
            postal_code: document.getElementById("postcode").value,
            city: document.getElementById("city").value,
          },
        },
      },
    });

    if (error) {
      // This will be a card decline, authentication error, etc.
      showMessage(error.message);
      setLoading(false);
    } else {
      // Payment succeeded. Now, create the order in our database.
      await createOrder(email);
    }
  }

  // Creates the final order in the backend
  async function createOrder(email) {
    const formData = new FormData(paymentForm);
    const formProps = Object.fromEntries(formData);

    const payload = {
      variant_id: paymentForm.dataset.variantId,
      quantity: paymentForm.dataset.quantity,
      keep_count: sessionStorage.getItem("keep_count") || 1, // Retrieve from session storage
      email: email,
      name: formProps.name,
      address: formProps.address,
      city: formProps.city,
      postcode: formProps.postcode,
      payment_intent_id: clientSecret.split("_secret")[0], // Extract PI from client_secret
    };

    try {
      const response = await fetch("/awakening/api/create-order/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const orderData = await response.json();

      if (orderData.success && orderData.redirect_url) {
        window.location.href = orderData.redirect_url; // Redirect to the dynamic success page
      } else {
        showMessage(orderData.error || "An unknown error occurred.");
        setLoading(false);
      }
    } catch (error) {
      console.error("Error creating order:", error);
      showMessage("Server error while finalizing order.");
      setLoading(false);
    }
  }

  // --- UI Helper Functions ---
  function showMessage(messageText) {
    const messageContainer = document.querySelector("#card-errors");
    messageContainer.textContent = messageText;
    messageContainer.style.opacity = 1;
    setTimeout(() => {
      messageContainer.style.opacity = 0;
    }, 5000);
  }

  function setLoading(isLoading) {
    if (!submitButton) return;

    if (isLoading) {
      submitButton.disabled = true;
      submitButton.innerHTML =
        '<span class="animate-pulse">PROCESSING ENCRYPTION...</span>';
    } else {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  }
});
