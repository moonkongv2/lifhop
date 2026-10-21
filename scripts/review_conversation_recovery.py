"""Review captured first responses offline. This command cannot call AI or modify conversations."""
import argparse
import json
from pathlib import Path
from app.evaluation.recovery_review import FirstResponseReview,review_capture
from app.evaluation.storage import PRIVATE_ROOT,read_private,write_private


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--response',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    request=read_private(args.request,PRIVATE_ROOT)
    response=read_private(args.response,PRIVATE_ROOT)
    review=FirstResponseReview.model_validate(read_private(args.review,PRIVATE_ROOT))
    report=review_capture(request,response,review)
    write_private(args.out,report,root=PRIVATE_ROOT)
    print(json.dumps(dict(conversation_verdict=report['conversation_verdict'],
        eligible_for_protocol=report['eligible_for_protocol'],provider_calls=0)))


if __name__=='__main__':main()
