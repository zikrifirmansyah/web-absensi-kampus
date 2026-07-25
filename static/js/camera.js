/**
 * initCamera - modul reusable untuk mengakses webcam & mengambil SATU foto.
 * Dipakai di halaman absen mahasiswa.
 *
 * options:
 *   videoId, canvasId, previewId, btnCaptureId, btnRetakeId : id elemen HTML
 *   onCapture(dataUrl) : dipanggil setelah foto diambil
 *   onRetake()         : dipanggil saat tombol "ambil ulang" ditekan
 */
function initCamera(options) {
  const video = document.getElementById(options.videoId);
  const canvas = document.getElementById(options.canvasId);
  const preview = document.getElementById(options.previewId);
  const btnCapture = document.getElementById(options.btnCaptureId);
  const btnRetake = document.getElementById(options.btnRetakeId);

  let stream = null;

  function startCamera() {
    navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 }, audio: false })
      .then(function (s) {
        stream = s;
        video.srcObject = stream;
      })
      .catch(function (err) {
        alert("Tidak dapat mengakses kamera: " + err.message + "\nPastikan izin kamera sudah diberikan pada browser.");
      });
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
  }

  btnCapture.addEventListener("click", function () {

    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.drawImage(video,0,0,canvas.width,canvas.height);

    const dataUrl = canvas.toDataURL("image/jpeg",0.9);

    hasilFoto = [dataUrl];

    renderThumbs();

    stopCamera();

    video.style.display="none";

    btnCapture.style.display="none";

    if(btnReset)
        btnReset.style.display="inline-block";

    if(typeof options.onComplete==="function"){
        options.onComplete(hasilFoto);
    }

});

  btnCapture.addEventListener("click", function () {

    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth || 480;
    canvas.height = video.videoHeight || 360;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);

    preview.src = dataUrl;
    preview.style.display = "block";

    stopCamera();

    video.style.display = "none";
    btnCapture.style.display = "none";

    if (btnRetake)
        btnRetake.style.display = "inline-block";

    if (typeof options.onCapture === "function") {
        options.onCapture(dataUrl);
    }

});

  startCamera();
}


/**
 * initMultiCamera - modul untuk mengambil BEBERAPA foto berurutan (dipakai saat
 * registrasi wajah mahasiswa agar data wajah lebih akurat, mis. 3 foto).
 *
 * options:
 *   videoId, canvasId, thumbsContainerId, btnCaptureId, btnResetId : id elemen HTML
 *   totalFoto     : jumlah foto yang harus diambil (default 3)
 *   labelInstruksiId : id elemen teks instruksi (opsional)
 *   onProgress(jumlahTerambil, total) : dipanggil tiap kali 1 foto berhasil diambil
 *   onComplete(dataUrlArray)          : dipanggil saat semua foto sudah terkumpul
 *   onReset()                         : dipanggil saat tombol reset ditekan
 */
function initMultiCamera(options) {
  const totalFoto = 1;
  const video = document.getElementById(options.videoId);
  const canvas = document.getElementById(options.canvasId);
  const thumbsContainer = document.getElementById(options.thumbsContainerId);
  const btnCapture = document.getElementById(options.btnCaptureId);
  const btnReset = document.getElementById(options.btnResetId);
  const labelInstruksi = options.labelInstruksiId ? document.getElementById(options.labelInstruksiId) : null;

  const instruksiList = [
    "Hadapkan wajah lurus ke kamera"
  ];

  let stream = null;
  let hasilFoto = [];

  function updateInstruksi() {
    if (!labelInstruksi) return;
    if (hasilFoto.length >= totalFoto) {
      labelInstruksi.textContent = "Semua foto berhasil diambil ✔";
      return;
    }
    const teks = instruksiList[hasilFoto.length] || "Ambil foto";
    labelInstruksi.textContent = `Foto ${hasilFoto.length + 1} dari ${totalFoto}: ${teks}`;
  }

  function startCamera() {
    navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 }, audio: false })
      .then(function (s) {
        stream = s;
        video.srcObject = stream;
        video.style.display = "block";
      })
      .catch(function (err) {
        alert("Tidak dapat mengakses kamera: " + err.message + "\nPastikan izin kamera sudah diberikan pada browser.");
      });
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
  }

  function renderThumbs() {
    thumbsContainer.innerHTML = "";
    hasilFoto.forEach(function (dataUrl) {
      const img = document.createElement("img");
      img.src = dataUrl;
      img.width = 70;
      img.height = 70;
      img.style.objectFit = "cover";
      img.style.borderRadius = "8px";
      img.style.border = "2px solid #198754";
      img.className = "me-2 mb-2";
      thumbsContainer.appendChild(img);
    });
  }

  btnCapture.addEventListener("click", function () {
    if (hasilFoto.length >= totalFoto) return;

    const ctx = canvas.getContext("2d");
    canvas.width = video.videoWidth || 480;
    canvas.height = video.videoHeight || 360;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    hasilFoto.push(dataUrl);
    renderThumbs();
    updateInstruksi();

    if (typeof options.onProgress === "function") {
      options.onProgress(hasilFoto.length, totalFoto);
    }

    if (hasilFoto.length >= totalFoto) {
      stopCamera();
      video.style.display = "none";
      btnCapture.style.display = "none";
      if (btnReset) btnReset.style.display = "inline-block";
      if (typeof options.onComplete === "function") {
        options.onComplete(hasilFoto.slice());
      }
    }
  });

  if (btnReset) {
    btnReset.addEventListener("click", function () {
      hasilFoto = [];
      renderThumbs();
      updateInstruksi();
      btnCapture.style.display = "inline-block";
      btnReset.style.display = "none";
      startCamera();
      if (typeof options.onReset === "function") {
        options.onReset();
      }
    });
  }

  updateInstruksi();
  startCamera();
}
