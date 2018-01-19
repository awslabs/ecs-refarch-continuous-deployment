echo "AWSRegionToAMI:"

for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)
do
  echo "  ${region}:"
  echo -n "    AMI: "

  aws ec2 describe-images \
    --owners amazon \
    --query 'reverse(sort_by(Images[?Name != `null`] | [?contains(Name, `amazon-ecs-optimized`) == `true`], &CreationDate))[:1].ImageId' \
    --output text \
    --region $region
done
