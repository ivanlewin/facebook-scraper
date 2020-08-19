# facebook-scraper

### Reaction types 
* 1: Like - Me gusta
* 2: Love - Me encanta
* 3: Wow - Me asombra
* 4: Haha - Me divierte
<!-- * 5: Yay -  -->
* 7: Sad - Me entristece
* 8: Angry - Me enoja
* 10: Confused - 
* 11: Thankful - 
* 12: Pride - 
* 16: Care - Me importa

<!-- https://developers.facebook.com/docs/graph-api/reference/post/   -->
<!-- https://developers.facebook.com/docs/graph-api/reference/v7.0/comment -->

<!-- regex: -->
<!-- # https://regex101.com/r/Mj0CMu/2 -->


<!-- 109323440782253_145220453859218?fields=actions,admin_creator,application,backdated_time,call_to_action,expanded_height,event,created_time,coordinates,comments_mirroring_domain,child_attachments,can_reply_privately,instagram_eligibility,id,icon,height,full_picture,expanded_width,is_expired,is_hidden,is_inline_created,is_popular,is_published,is_spherical,is_instagram_eligible,message,from,message_tags,parent_id,picture,place,privacy,properties,scheduled_publish_time,shares,status_type,story,story_tags,subscribed,target,targeting,timeline_visibility,updated_time,via,width -->


driver.get(post_mobile)
with open("page_source_mobile_chrome_all_comments.html", "w+", encoding="utf-8") as f:
    f.write(driver.page_source)

# posts
prueba = {
    # 'evaluan' a lo mismo
    "posts_pname": "https://m.facebook.com/kicillofok/posts/1677972215701943",
    "posts_pid": "https://m.facebook.com/116053261893854/posts/1677972215701943",
    "story_php": "https://m.facebook.com/story.php?story_fbid=1677972215701943&id=116053261893854",

    # 'evaluan' a lo mismo
    "photos_phid": "https://m.facebook.com/kicillofok/photos/pcb.1677972215701943/1677971219035376/",
    "photo_php": "https://m.facebook.com/photo.php?fbid=1677971219035376&set=a.211840645648448",

    # 'evaluan' a lo mismo
    "photo_php_1": "https://m.facebook.com/photo.php?fbid=10158620472653554&set=a.10150354952758554",
    "photos_a_1": "https://m.facebook.com/GrandMartez/photos/a.10150354952758554/10158620472653554",

    "story_php_livevideo": "https://m.facebook.com/story.php?story_fbid=951485155323874&id=153080620724",

    "watch": "https://m.facebook.com/watch/?v=276697480251803"
}
