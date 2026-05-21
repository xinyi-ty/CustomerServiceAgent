/* ================= 字数统计功能 ================= */

/*获取输入框*/
const userText=document.getElementById("userText");

/**找到：id="userText"这个输入框。以后JS才能操作它 **/

/*获取字数统计区域*/
const counter=document.querySelector(".counter");

/*监听输入事件*/
/**input作用：监听用户在输入**/
userText.addEventListener("input",function(){
    let currentLength=userText.value.length;
    /*获取当前输入内容长度 */


    /*更新页面文字*/
    counter.textContent=currentLength+"/1000";}
)

/* ================= 上传文件功能 ================= */
/*获取上传按钮*/ 
const uploadBtn=document.getElementById("uploadBtn");

/*获取文件输入框*/ 
const uploadInput=document.getElementById("uploadInput"); 

/*获取显示区域*/ 
const fileInfo=document.getElementById("fileInfo");

/** 点击按钮触发文件选择*/
uploadBtn.addEventListener("click",function(){
    uploadInput.click();
}
);

/*监听文件变化*/ 
uploadInput.addEventListener("change",function(){
    /*获取第一个文件*/ 
    const file=uploadInput.files[0];

    if(!file){
        return;
    }

    let fileSize=file.size/1024/1024;

    let allowedTypes=[
        "image/jpeg",

        "image/png",

        "image/jpg",

        "video/mp4",

        "video/quicktime",

        "video/x-msvideo"
    ];
    /*格式检查*/ 
    if(!allowedTypes.inclides(file.type)){
    alert("仅支持图片或视频格式");  
    return;
}

    /* 大小检查*/
    if(fileSize>50){
    alert("文件不能超过50MB");
    return;
} 

    /* 显示上传结果*/
    fileInfo.textContent="已上传"+file.name;
});

/* ================= 提交按钮功能 ================= */

/*获取提交按钮*/
const submitBtn=document.getElementById("submitBtn");

/* 监听点击事件*/
submitBtn.addEventListener("click",function(){
    /*获取输入内容*/
    let content=userText.value.trim();

    /*空输入检查*/
    if(content===""){
        alert("请输入问题描述");
        return;
    }

    alert( "提交成功");

}
);