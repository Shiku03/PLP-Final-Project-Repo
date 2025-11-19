//redirect to sign-in page function
function redirectToPage(url){
    window.location.href=url;
}
//show sign-in form function

//sign-in form validation function



//generate video function

//upload files function
function uploadFile(uploadedFile){
    document.getElementById("upload-btn").addEventListener("click", async()=>{
        const fileInput=document.getElementById("uploadedFile");
        const fileStatus=document.getElementById("status");

        if(fileInput.files.length===0){
            fileStatus.textContent="Please select a file to upload.";
            return;
        }

        const file=fileInput.files[0];
        const formData = new FormData();
        formData.append("file", file);

        fileStatus.textContent="Uploading...";

        try{
const response = await fetch("/upload", {
    method: "POST",
    body: formData,
});

 const result = await response.json();
    fileStatus.textContent=result.message;
        }
        catch(error){
            fileStatus.textContent="An error occurred during upload. Please try again.";
            console.error("Upload error:", error);
        }
    });
}